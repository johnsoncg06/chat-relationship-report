#!/usr/bin/env python3
"""打包後的煙霧測試：對執行中的 App 上傳一份合成 LINE 聊天，跑完整流程，檢查主要欄位。
用法: python tests/smoke.py <port> <token>   （失敗時以非零結束碼退出，讓 CI 擋下發布）"""
import sys, json, time, random, urllib.request, urllib.parse, urllib.error
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
port, tok = sys.argv[1], sys.argv[2]
B = f'http://127.0.0.1:{port}'
def call(path, data=None):
    sep = '&' if '?' in path else '?'
    req = urllib.request.Request(f'{B}{path}{sep}t={tok}', data=data, method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=180) as r: return r.read()
random.seed(7); L = ['[LINE] 與測試的聊天記錄', '儲存日期： 2026/11/26 10:24', '']
for d in range(60):
    day = 1 + d; mo = 9 + (day - 1) // 30; dd = (day - 1) % 30 + 1
    L.append(f'2026/{mo:02d}/{dd:02d}（四）')
    for i in range(random.randint(25, 60)):
        L.append(f'{9 + i // 6:02d}:{(i * 9) % 60:02d}\t{"小明" if i % 2 == 0 else "小華"}\t{random.choice(["晚安", "哈哈哈", "你在幹嘛", "我們去吃飯", "好啊", "想你", "[貼圖]"])}')
    L.append('')
for _ in range(40):   # 連線稍慢時多試幾次
    try: call('/ping'); break
    except Exception: time.sleep(1)
call('/reset', b''); call('/upload?name=smoke.txt', '\n'.join(L).encode('utf-8'))
d = json.loads(call('/run', json.dumps({'tz': '8', 'ctx': {'met': 'online_blind_date', 'stage': 'not_met_sns', 'breakup': 'one'}}).encode()))
assert not d.get('error'), d
assert d['stats']['total'] > 1000, d['stats']['total']
assert 0 <= d['score']['closeness'] <= 100
assert d['score'].get('experimental') is not None
sc = d['score']; assert sc.get('profile') == 'tw' and sc.get('weights') and sc.get('evidence_levels'), 'profile fields missing'
assert set(sc['closeness_by_profile']) == {'base', 'tw'} and '表達量' in sc['weights']
assert all(v in ('未驗證', '東亞參考', '西方參考（實驗性）', '台灣驗證') for v in sc['evidence_levels'].values())
assert any(k.get('sticker') for k in d['stats']['kinds'].values()), 'sticker kind not counted'
assert 'calls' in d['stats']
cx = sc.get('context'); assert cx and cx['met'] == 'online_blind_date' and len(cx['notes']) == 3 and cx['adjustments'], cx
assert d['forecast'].get('caveats') and any('剛失戀' in c for c in d['forecast']['caveats']), d['forecast'].get('caveats')
assert d.get('forecast') and d['forecast'].get('scenarios'), 'forecast missing: ' + str(d.get('notes'))
GOLD = {'closeness': d['score']['closeness'], 'romantic': d['score']['romantic_signal'], 'dims': d['score']['dimensions'], 'band': d['score']['band'], 'total': d['stats']['total'],
        'fade': d['forecast']['fade_risk_4wk'], 'scen': {k: v['point'] for k, v in d['forecast']['scenarios'].items()}}
print('GOLD ' + json.dumps(GOLD, ensure_ascii=False, sort_keys=True))
import os as _os
_gf = _os.environ.get('GOLD_FILE')   # CI：先用原始碼跑一次寫入基準，打包後的 App 再跑一次比對，確保精簡／打包不改變任何分數與預測
if _gf:
    if not _os.path.isfile(_gf): open(_gf, 'w', encoding='utf-8').write(json.dumps(GOLD, ensure_ascii=False, sort_keys=True))
    else:
        base = json.load(open(_gf, encoding='utf-8'))
        for k in ('closeness', 'romantic', 'dims', 'band', 'total'): assert base[k] == GOLD[k], f'packaged result differs from source: {k}: {base[k]} vs {GOLD[k]}'
        assert abs(base['fade'] - GOLD['fade']) <= .05 and all(abs(base['scen'][k] - GOLD['scen'][k]) <= 4 for k in base['scen']), 'forecast differs from source build'
        print('PARITY OK (packaged == source)')
assert len(d['images']) >= 5, d['images']
mo = d.get('monthly'); assert mo and len(mo['months']) >= 2 and all(m.get('title') for m in mo['months']), 'monthly recap missing'
assert sum(m['total'] for m in mo['months']) == d['stats']['total'], 'monthly totals must add up to total messages'
assert isinstance(d.get('alerts', {}).get('alerts'), list), 'alerts missing'
# --- 早期模式：16 天、後 7 天明顯變冷的合成聊天，要有 early 區塊且判斷為「高」---
E = ['[LINE] 與測試的聊天記錄', '儲存日期： 2026/11/26 10:24', '']
random.seed(11)
for ed in range(16):
    E.append(f'2026/11/{ed + 1:02d}（四）')
    cool = ed >= 9; n = random.randint(4, 8) if cool else random.randint(30, 45); t = 9 * 60
    for i in range(n):
        t += random.randint(40, 180) if cool else random.randint(1, 6); h, m = divmod(t, 60)
        who = '小明' if (i % 5 != 4 if cool else i % 2 == 0) else '小華'
        E.append(f'{h % 24:02d}:{m:02d}\t{who}\t' + (random.choice(['嗯', '好', '改天再說', '最近比較忙']) if cool else random.choice(['你在幹嘛', '哈哈哈', '吃飯了嗎', '晚安', '我們去吃那間'])))
    E.append('')
call('/reset', b''); call('/upload?name=early.txt', '\n'.join(E).encode('utf-8'))
de = json.loads(call('/run', json.dumps({'tz': '8', 'ctx': {'met': 'new'}}).encode()))
assert not de.get('error'), de
fe = de.get('forecast'); assert fe and fe.get('mode') == 'early' and fe.get('early'), 'early mode missing: ' + str(de.get('notes'))
assert fe['early']['risk_label'].startswith('高'), fe['early']['risk_label']
assert len(fe['early']['signals']) >= 6 and not fe.get('scenarios')
assert any(x['type'] == 'fall' and x['level'] == 'high' and x['advice'] for x in de['alerts']['alerts']), de['alerts']
# --- 升溫的早期聊天：要有「可能突破」提醒 ---
W = ['[LINE] 與測試的聊天記錄', '儲存日期： 2026/11/26 10:24', '']
random.seed(5)
for wd_ in range(16):
    W.append(f'2026/11/{wd_ + 1:02d}（四）'); warm = wd_ >= 9; n = random.randint(40, 55) if warm else random.randint(8, 14); t = 9 * 60
    for i in range(n):
        t += random.randint(1, 5) if warm else random.randint(30, 90); h, m = divmod(t, 60)
        W.append(f'{h % 24:02d}:{m:02d}\t{"小明" if i % 2 == 0 else "小華"}\t' + random.choice(['你在幹嘛', '哈哈哈', '想你', '晚安', '好想見你', '明天一起吃飯']))
    W.append('')
call('/reset', b''); call('/upload?name=warm.txt', '\n'.join(W).encode('utf-8'))
dw = json.loads(call('/run', json.dumps({'tz': '8', 'ctx': {'met': 'new'}}).encode())); assert not dw.get('error'), dw
assert any(x['type'] == 'breakthrough' for x in dw['alerts']['alerts']), (dw['forecast'].get('early', {}).get('risk_label'), dw['alerts'])
call('/reset', b''); call('/upload?name=early.txt', '\n'.join(E).encode('utf-8'))
# --- 歷史紀錄：選資料夾 → 再分析一次（自動存檔）→ 列表 / 載入 / 比對 / 回測 / 刪除 ---
import tempfile, os
def jcall(path, obj=None):
    return json.loads(call(path, None if obj is None else json.dumps(obj).encode()))
folder = os.path.join(tempfile.mkdtemp(prefix='chatrel_hist_'), 'data')
assert jcall('/api/folder', {'path': folder}).get('folder'), 'set folder failed'
ids = []
for lab in ('smoke-1', 'smoke-2'):
    call('/reset', b''); call('/upload?name=smoke.txt', '\n'.join(L).encode('utf-8'))
    r = json.loads(call('/run', json.dumps({'tz': '8', 'label': lab}).encode())); assert r.get('saved_run'), r.get('notes'); ids.append(r['saved_run']); time.sleep(1.1)
h = jcall('/api/history'); assert len(h['runs']) == 2 and h['folder'], h
assert 'evidence' not in jcall('/api/run?id=' + ids[0])['score'], 'evidence must not be stored'
c = jcall('/api/compare?a=%s&b=%s' % (ids[0], ids[1])); assert c['rows'], c
assert jcall('/api/run_update', {'id': ids[1], 'label': 'x'}).get('ok')
assert jcall('/api/run_delete', {'id': ids[0]}).get('ok') and len(jcall('/api/history')['runs']) == 1
# --- 多對象（專案）：建立兩個對象 → 指定紀錄 → 同一組名字自動歸隊 → 早期模式對象也能並排 → 改名／刪除 ---
pa = jcall('/api/project_create', {'name': '小華'})['id']; pb = jcall('/api/project_create', {'name': '早期對象'})['id']
try: jcall('/api/project_create', {'name': '小華'}); raise SystemExit('duplicate project name must be rejected')
except urllib.error.HTTPError as ex: assert ex.code == 400
assert jcall('/api/run_assign', {'id': ids[1], 'project': pa}).get('ok')
call('/reset', b''); call('/upload?name=smoke.txt', '\n'.join(L).encode('utf-8'))
r3 = json.loads(call('/run', json.dumps({'tz': '8', 'me': '小明'}).encode())); assert r3.get('saved_run')
assert jcall('/api/run?id=' + r3['saved_run'])['meta']['project'] == pa, 'same pair must auto-join its project'
call('/reset', b''); call('/upload?name=early.txt', '\n'.join(E).encode('utf-8')); time.sleep(1.1)
r4 = json.loads(call('/run', json.dumps({'tz': '8', 'ctx': {'met': 'new'}, 'project': pb}).encode())); assert r4.get('saved_run')
po = jcall('/api/projects'); by = {p['name']: p for p in po['projects']}
assert by['小華']['n'] == 2 and by['早期對象']['n'] == 1 and not po['unassigned'], po
assert by['小華']['latest']['digest']['mode'] == 'full' and by['小華']['latest']['digest']['future'], 'full digest missing'
assert by['早期對象']['latest']['digest']['mode'] == 'early' and by['早期對象']['latest']['digest']['risk'].startswith('高')
pp = jcall('/api/personal'); assert pp['n_used'] == 1 and pp['skipped'] >= 1 and pp['archetype'] and pp['runs'][0]['score'] is not None, pp
assert '渣' not in json.dumps(pp['archetype'], ensure_ascii=False), 'no condemning labels'
assert jcall('/api/project_rename', {'id': pb, 'name': '改名'}).get('ok')
assert jcall('/api/project_delete', {'id': pb}).get('ok') and len(jcall('/api/projects')['unassigned']) == 1, 'delete must keep runs as unassigned'

# --- 問答（自帶 API Key）：用本機假伺服器驗證，不連外網
import threading, http.server
SEEN = {}
class _Mock(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers['Content-Length']))); SEEN['key'] = self.headers.get('x-api-key'); SEEN['body'] = json.dumps(b, ensure_ascii=False)
        out = json.dumps({'content': [{'type': 'text', 'text': '分數是 72'}], 'usage': {'input_tokens': 1, 'output_tokens': 1}}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
_srv = http.server.HTTPServer(('127.0.0.1', 8798), _Mock); threading.Thread(target=_srv.serve_forever, daemon=True).start()
ac = jcall('/api/ask_cfg'); assert ac['tls'] and not ac['has_key'] and ac['has_result'], ac
try: jcall('/api/ask', {'question': 'hi'}); raise SystemExit('ask without key must fail')
except urllib.error.HTTPError as e: assert e.code == 400
try: jcall('/api/ask_cfg', {'api_key': 'bad'}); raise SystemExit('bad key must be rejected')
except urllib.error.HTTPError as e: assert e.code == 400
KEY = 'sk-ant-' + 'x' * 30
assert jcall('/api/ask_cfg', {'api_key': KEY}).get('ok') and jcall('/api/ask_cfg')['has_key']
ans = jcall('/api/ask', {'question': '分數是多少？', 'history': []}); assert ans['answer'] == '分數是 72' and SEEN['key'] == KEY
assert '分數是多少' in SEEN['body'] and 'closeness' in SEEN['body'], 'context must carry computed numbers'
assert '小明' not in SEEN['body'] and '小華' not in SEEN['body'], 'names must be pseudonymised before sending'
assert jcall('/api/ask_cfg', {'api_key': ''}).get('ok') and not jcall('/api/ask_cfg')['has_key']
call('/quit', b'')
print('SMOKE OK closeness=%s' % d['score']['closeness'])
