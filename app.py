#!/usr/bin/env python3
"""聊天關係報告 — 桌面 App（本機執行，資料不離開你的電腦）。
啟動後會在本機開一個只有你能連的網頁介面（127.0.0.1），上傳 LINE .txt / IG .json 即可產出分數、圖表、預測。
只用 Python 標準函式庫＋ pandas / numpy / scipy / matplotlib。"""
import os, sys, io, json, glob, shutil, tempfile, secrets, threading, webbrowser, runpy, zipfile, contextlib, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

for _n in ('stdout', 'stderr'):   # Windows 主控台常是 cp1252 / 視窗模式下為 None：避免印中文就崩潰
    _s = getattr(sys, _n, None)
    if _s is None: setattr(sys, _n, open(os.devnull, 'w', encoding='utf-8'))
    else:
        try: _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass

BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, 'scripts')
TOKEN = os.environ.get('CHATREL_TOKEN') or secrets.token_urlsafe(16)   # CHATREL_TOKEN 僅供自動化測試
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


def page():
    return open(os.path.join(BASE, 'web', 'index.html'), 'rb').read()


LAST_PING = [0.0]


def find_app_browser():
    """找 Edge / Chrome，用 --app 模式開成像獨立 App 的視窗；找不到就用預設瀏覽器。"""
    c = []
    if sys.platform.startswith('win'):
        for env in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            r = os.environ.get(env)
            if r:
                c += [os.path.join(r, 'Microsoft', 'Edge', 'Application', 'msedge.exe'), os.path.join(r, 'Google', 'Chrome', 'Application', 'chrome.exe')]
    elif sys.platform == 'darwin':
        c = ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser']
    else:
        c = [shutil.which(x) or '' for x in ('microsoft-edge', 'google-chrome', 'chromium', 'chromium-browser')]
    return next((x for x in c if x and os.path.exists(x)), None)


def open_window(url):
    exe = find_app_browser()
    if exe:
        try:
            import subprocess
            prof = os.path.join(WORK, 'browser_profile'); os.makedirs(prof, exist_ok=True)
            subprocess.Popen([exe, f'--app={url}', '--window-size=1200,820', f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    webbrowser.open(url)


def watchdog():
    """視窗關閉後（約 2 分鐘沒有心跳）自動結束，避免背景殘留。"""
    import time
    while True:
        time.sleep(5)
        if LAST_PING[0] and time.time() - LAST_PING[0] > 120:
            shutil.rmtree(WORK, ignore_errors=True); os._exit(0)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _ok(self, code=200, ctype='application/json', body=b''):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)

    def _auth(self):
        if self.path.startswith('/favicon'): self._ok(204, 'image/x-icon', b''); return None
        q = parse_qs(urlparse(self.path).query)
        if q.get('t', [''])[0] != TOKEN: self._ok(403, 'text/plain', b'forbidden'); return None
        return q

    def do_GET(self):
        u = urlparse(self.path); q = self._auth()
        if q is None: return
        if u.path == '/ping':
            import time; LAST_PING[0] = time.time(); return self._ok(body=b'{}')
        if u.path == '/': return self._ok(200, 'text/html; charset=utf-8', page())
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
        if u.path == '/quit':
            self._ok(body=b'{}'); shutil.rmtree(WORK, ignore_errors=True); threading.Timer(0.3, lambda: os._exit(0)).start(); return
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
    if not os.environ.get('NO_BROWSER'): threading.Timer(0.6, lambda: open_window(url)).start()
    threading.Thread(target=watchdog, daemon=True).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: shutil.rmtree(WORK, ignore_errors=True)


if __name__ == '__main__':
    main()
