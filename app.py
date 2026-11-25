#!/usr/bin/env python3
"""聊天關係報告 — 桌面 App（本機執行，資料不離開你的電腦）。
啟動後會在本機開一個只有你能連的網頁介面（127.0.0.1），上傳 LINE .txt / IG .json 即可產出分數、圖表、預測。
只用 Python 標準函式庫＋ pandas / numpy / scipy / matplotlib。"""
import os, sys, io, json, glob, shutil, tempfile, secrets, threading, webbrowser, runpy, zipfile, contextlib, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, 'scripts')
TOKEN = secrets.token_urlsafe(16)
WORK = tempfile.mkdtemp(prefix='chatrel_')
LOCK = threading.Lock()


def run_script(name, argv):
    """在同一個行程內執行腳本（打包成執行檔後也能用），回傳 (stdout 文字, 錯誤文字)。"""
    old = sys.argv; buf = io.StringIO(); err = ''
    sys.argv = [name] + [str(a) for a in argv]
    try:
        with contextlib.redirect_stdout(buf):
            try: runpy.run_path(os.path.join(SCRIPTS, name), run_name='__main__')
            except SystemExit: pass
    except Exception:
        err = traceback.format_exc(limit=4)
    finally:
        sys.argv = old
    return buf.getvalue(), err


def load_json(text):
    try: return json.loads(text)
    except Exception: return None


def pipeline(p):
    """依序跑 stats → score → charts → forecast → dashboard，回傳給前端的結果字典。"""
    shutil.rmtree(os.path.join(WORK, 'out'), ignore_errors=True)
    out = os.path.join(WORK, 'out'); os.makedirs(out)
    up = os.path.join(WORK, 'uploads')
    files = sorted(glob.glob(os.path.join(up, '*')))
    if not files: return {'error': '還沒有上傳檔案'}
    argv = files + ['--export-csv', os.path.join(out, 'messages.csv'), '--tz', p.get('tz') or '8']
    if p.get('me'): argv += ['--me', p['me']]
    if p.get('since'): argv += ['--since', p['since']]
    if p.get('until'): argv += ['--until', p['until']]
    for x in (p.get('exclude') or '').split(','):
        if x.strip(): argv += ['--exclude', x.strip()]
    for x in (p.get('alias') or '').split(','):
        if '=' in x: argv += ['--alias', x.strip()]
    txt, err = run_script('chat_stats.py', argv)
    stats = load_json(txt)
    if err or stats is None: return {'error': '統計失敗：' + (err or txt[:300] or '沒有輸出')}
    if 'error' in stats: return {'error': '無法分析：' + json.dumps(stats, ensure_ascii=False)}
    open(os.path.join(out, 'stats.json'), 'w', encoding='utf-8').write(txt)
    txt, err = run_script('score_intimacy.py', [os.path.join(out, 'stats.json')])
    score = load_json(txt)
    if err or score is None: return {'error': '評分失敗：' + (err or txt[:300])}
    open(os.path.join(out, 'score.json'), 'w', encoding='utf-8').write(txt)
    csv_p, st_p, sc_p = os.path.join(out, 'messages.csv'), os.path.join(out, 'stats.json'), os.path.join(out, 'score.json')
    notes = []
    chart_dir = os.path.join(out, 'charts')
    _, err = run_script('chat_charts.py', [csv_p, st_p, sc_p, chart_dir])
    if err: notes.append('圖表產生失敗：' + err.strip().splitlines()[-1])
    fc = None
    if not stats.get('is_group') and score.get('dimensions'):
        txt, err = run_script('forecast.py', [csv_p, st_p, sc_p])
        fc = load_json(txt)
        if err or fc is None: notes.append('預測失敗：' + (err.strip().splitlines()[-1] if err else txt[:200])); fc = None
        elif 'error' in fc:
            notes.append('未做預測：' + ('需要至少 8 週的資料' if fc['error'] == 'need_8_weeks' else '只適用二人聊天')); fc = None
        else:
            fp = os.path.join(out, 'forecast.json'); open(fp, 'w', encoding='utf-8').write(txt)
            _, err = run_script('chat_dashboard.py', [csv_p, st_p, sc_p, fp, chart_dir])
            if err: notes.append('總覽圖失敗：' + err.strip().splitlines()[-1])
    imgs = sorted(os.path.basename(f) for f in glob.glob(os.path.join(chart_dir, '*.png')))
    return {'stats': stats, 'score': score, 'forecast': fc, 'images': imgs, 'notes': notes}


PAGE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>聊天關係報告</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1f2328;--mute:#6b7280;--line:#e5e7eb;--blue:#2a6fdb;--warn:#b45309}
@media(prefers-color-scheme:dark){:root{--bg:#16181c;--card:#1f2228;--ink:#e6e8eb;--mute:#9aa3ad;--line:#2d313a;--blue:#6aa0ff;--warn:#f0b35a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang TC","Microsoft JhengHei",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 60px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mute);margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
h2{font-size:16px;margin:0 0 10px}label{display:block;font-size:13px;color:var(--mute);margin:8px 0 3px}
input[type=text],input[type=date]{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:transparent;color:var(--ink)}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
button{background:var(--blue);color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer}button:disabled{opacity:.5}
button.ghost{background:transparent;color:var(--blue);border:1px solid var(--blue)}
.drop{border:2px dashed var(--line);border-radius:12px;padding:26px;text-align:center;color:var(--mute);cursor:pointer}.drop.on{border-color:var(--blue)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}.kpi{border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.kpi b{display:block;font-size:26px;color:var(--blue)}.kpi span{color:var(--mute);font-size:13px}
.bar{height:10px;border-radius:5px;background:var(--line);position:relative;margin:3px 0 9px}.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:var(--blue)}
.bar em{position:absolute;top:-2px;bottom:-2px;border-radius:3px;background:rgba(232,89,12,.35)}
.warn{color:var(--warn);margin:4px 0}.small{font-size:13px;color:var(--mute)}
.imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}.imgs img{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}
table{width:100%;border-collapse:collapse}td,th{padding:6px 4px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}
</style></head><body><main>
<h1>聊天關係報告</h1><div class="sub">資料只在你的電腦上處理，不會上傳。支援 LINE .txt、Instagram .json（可多選、可兩平台合併）。</div>
<div class="card"><h2>1. 選擇聊天記錄</h2>
<div class="drop" id="drop">把檔案拖到這裡，或點此選擇<br><span class="small">LINE：.txt　IG：message_1.json…</span><input id="file" type="file" multiple hidden></div>
<div id="flist" class="small" style="margin-top:8px"></div></div>
<div class="card"><h2>2. 設定（可略過）</h2><div class="row">
<div><label>你的名字（--me）</label><input type="text" id="me" placeholder="與聊天室顯示的名字相同"></div>
<div><label>排除機器人／系統帳號（逗號分隔）</label><input type="text" id="exclude" placeholder="例：LINE官方帳號,活動機器人"></div>
<div><label>合併名字（IG名=LINE名，逗號分隔）</label><input type="text" id="alias"></div>
<div><label>只分析從</label><input type="date" id="since"></div><div><label>到（不含）</label><input type="date" id="until"></div>
<div><label>時區（小時，台灣 8）</label><input type="text" id="tz" value="8"></div></div></div>
<button id="go" disabled>開始分析</button> <span id="status" class="small"></span>
<div id="result" style="margin-top:18px"></div>
</main><script>
const T=new URLSearchParams(location.search).get('t');const $=id=>document.getElementById(id);let uploaded=[];
const api=(p,o)=>fetch(p+(p.includes('?')?'&':'?')+'t='+T,o);
$('drop').onclick=()=>$('file').click();
['dragover','dragenter'].forEach(e=>$('drop').addEventListener(e,ev=>{ev.preventDefault();$('drop').classList.add('on')}));
['dragleave','drop'].forEach(e=>$('drop').addEventListener(e,ev=>{ev.preventDefault();$('drop').classList.remove('on')}));
$('drop').addEventListener('drop',ev=>send(ev.dataTransfer.files));$('file').onchange=ev=>send(ev.target.files);
async function send(fs){await api('/reset',{method:'POST'});uploaded=[];$('flist').textContent='上傳中…';
 for(const f of fs){const r=await api('/upload?name='+encodeURIComponent(f.name),{method:'POST',body:await f.arrayBuffer()});if(r.ok)uploaded.push(f.name)}
 $('flist').textContent=uploaded.length?'已選：'+uploaded.join('、'):'';$('go').disabled=!uploaded.length}
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
$('go').onclick=async()=>{$('go').disabled=true;$('status').textContent='分析中…（大型聊天可能要一分鐘）';$('result').innerHTML='';
 const body={};['me','exclude','alias','since','until','tz'].forEach(k=>body[k]=$(k).value.trim());
 const r=await api('/run',{method:'POST',body:JSON.stringify(body)});const d=await r.json();$('go').disabled=false;$('status').textContent='';render(d)};
function render(d){const R=$('result');if(d.error){R.innerHTML='<div class="card warn">'+esc(d.error)+'</div>';return}
 const s=d.score,st=d.stats,f=d.forecast;let h='';
 h+='<div class="card"><h2>結論</h2><div class="kpis"><div class="kpi"><b>'+s.closeness+'</b><span>親密度 /100</span></div><div class="kpi"><b>'+s.romantic_signal+'</b><span>浪漫訊號 /100</span></div><div class="kpi"><b>'+esc(s.trend)+'</b><span>趨勢</span></div><div class="kpi"><b>'+esc(s.confidence)+'</b><span>信心</span></div><div class="kpi"><b>'+st.total+'</b><span>訊息數</span></div></div>';
 h+='<p style="margin:12px 0 4px"><b>區間：</b>'+esc(s.band)+'</p><div class="small">'+Object.entries(st.people).map(([k,v])=>esc(k)+' '+v+' 則').join('　')+'</div></div>';
 const W=[].concat(s.warnings||[],d.notes||[]);if(W.length)h+='<div class="card"><h2>⚠ 健檢警告（請先看）</h2>'+W.map(w=>'<div class="warn">'+esc(w)+'</div>').join('')+'</div>';
 if(s.dimensions){h+='<div class="card"><h2>五維度</h2>'+Object.entries(s.dimensions).map(([k,v])=>'<div>'+esc(k)+' <b>'+v+'</b></div><div class="bar"><i style="width:'+v+'%"></i></div>').join('')+'</div>'}
 if(f){const sc=f.scenarios;const ks=Object.keys(sc).sort((a,b)=>sc[b].point-sc[a].point);
  h+='<div class="card"><h2>未來 8 週關係落點（相對可能性・啟發式・未校準）</h2><table>'+ks.map(k=>'<tr><td style="width:34%">'+esc(k)+(k===f.current_band_scenario?' <span class="small">（目前）</span>':'')+'</td><td><div class="bar" style="margin:0"><i style="width:'+sc[k].point+'%"></i><em style="left:'+sc[k].p10+'%;width:'+Math.max(1,sc[k].p90-sc[k].p10)+'%"></em></div></td><td style="width:120px"><b>'+sc[k].point+'%</b> <span class="small">('+sc[k].p10+'–'+sc[k].p90+')</span></td></tr>').join('')+'</table>';
  h+='<p class="small">'+esc(f.scenario_note)+'</p><p class="small">淡出風險（4 週）：'+Math.round(f.fade_risk_4wk*100)+'%；訊息量近期斜率 '+f.trend_slope_pct_per_week+'%/週。</p></div>';
  if(f.rule_advice&&f.rule_advice.length)h+='<div class="card"><h2>目前建議（依資料）</h2><ul>'+f.rule_advice.map(a=>'<li>'+esc(a)+'</li>').join('')+'</ul><div class="small">建議僅描述行為，不代表對方的想法，也不替你做決定。</div></div>'}
 if(d.images.length)h+='<div class="card"><h2>圖表</h2><div class="imgs">'+d.images.map(i=>'<img src="/img/'+i+'?t='+T+'">').join('')+'</div></div>';
 h+='<div class="card"><button class="ghost" onclick="location.href=\'/download.zip?t='+T+'\'">下載全部結果（zip）</button> <span class="small">內含 stats / score / forecast JSON、逐則明細 CSV、所有圖表。想要敘事報告，可把 scorecard 或 score.json 貼給 Claude。</span></div>';
 h+='<div class="small">限制：只看文字；門檻為經驗設定、未用大樣本校準；機率為啟發式分數，不是真實機率；電話與見面看不到，分數是下限估計。</div>';R.innerHTML=h}
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _ok(self, code=200, ctype='application/json', body=b''):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)

    def _auth(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get('t', [''])[0] != TOKEN: self._ok(403, 'text/plain', b'forbidden'); return None
        return q

    def do_GET(self):
        u = urlparse(self.path); q = self._auth()
        if q is None: return
        if u.path == '/': return self._ok(200, 'text/html; charset=utf-8', PAGE.encode())
        if u.path.startswith('/img/'):
            f = os.path.join(WORK, 'out', 'charts', os.path.basename(u.path))
            if os.path.isfile(f): return self._ok(200, 'image/png', open(f, 'rb').read())
        if u.path == '/download.zip':
            buf = io.BytesIO(); root = os.path.join(WORK, 'out')
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                for dp, _, fs in os.walk(root):
                    for fn in fs: z.write(os.path.join(dp, fn), os.path.relpath(os.path.join(dp, fn), root))
            data = buf.getvalue(); self.send_response(200); self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename=chat_report.zip'); self.send_header('Content-Length', str(len(data))); self.end_headers()
            return self.wfile.write(data)
        self._ok(404, 'text/plain', b'not found')

    def do_POST(self):
        u = urlparse(self.path); q = self._auth()
        if q is None: return
        n = int(self.headers.get('Content-Length') or 0); body = self.rfile.read(n) if n else b''
        up = os.path.join(WORK, 'uploads')
        if u.path == '/reset':
            shutil.rmtree(up, ignore_errors=True); os.makedirs(up); return self._ok(body=b'{}')
        if u.path == '/upload':
            os.makedirs(up, exist_ok=True)
            name = os.path.basename(q.get('name', ['file'])[0]) or 'file'
            i = len(os.listdir(up)); open(os.path.join(up, f'{i:03d}_{name}'), 'wb').write(body)
            return self._ok(body=b'{}')
        if u.path == '/run':
            with LOCK:
                try: res = pipeline(json.loads(body or b'{}'))
                except Exception: res = {'error': '執行失敗：' + traceback.format_exc(limit=3)}
            return self._ok(body=json.dumps(res, ensure_ascii=False).encode())
        self._ok(404, 'text/plain', b'not found')


def main():
    if sys.stdout is None: sys.stdout = open(os.devnull, 'w')   # 無主控台環境避免 print 當掉
    srv = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', 0))), H)
    url = f'http://127.0.0.1:{srv.server_address[1]}/?t={TOKEN}'
    print('聊天關係報告已啟動：', url, '\n（關閉此視窗即結束；資料只存在本機暫存資料夾）', flush=True)
    if not os.environ.get('NO_BROWSER'): threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: shutil.rmtree(WORK, ignore_errors=True)


if __name__ == '__main__':
    main()
