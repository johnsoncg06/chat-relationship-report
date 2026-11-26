#!/usr/bin/env python3
"""打包後的煙霧測試：對執行中的 App 上傳一份合成 LINE 聊天，跑完整流程，檢查主要欄位。
用法: python tests/smoke.py <port> <token>   （失敗時以非零結束碼退出，讓 CI 擋下發布）"""
import sys, json, time, random, urllib.request, urllib.parse
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
assert len(d['images']) >= 5, d['images']
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
call('/quit', b'')
print('SMOKE OK closeness=%s' % d['score']['closeness'])
