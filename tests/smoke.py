#!/usr/bin/env python3
"""打包後的煙霧測試：對執行中的 App 上傳一份合成 LINE 聊天，跑完整流程，檢查主要欄位。
用法: python tests/smoke.py <port> <token>   （失敗時以非零結束碼退出，讓 CI 擋下發布）"""
import sys, json, time, random, urllib.request, urllib.parse
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
        L.append(f'{9 + i // 6:02d}:{(i * 9) % 60:02d}\t{"小明" if i % 2 == 0 else "小華"}\t{random.choice(["晚安", "哈哈哈", "你在幹嘛", "我們去吃飯", "好啊", "想你"])}')
    L.append('')
for _ in range(40):   # 連線稍慢時多試幾次
    try: call('/ping'); break
    except Exception: time.sleep(1)
call('/reset', b''); call('/upload?name=smoke.txt', '\n'.join(L).encode('utf-8'))
d = json.loads(call('/run', json.dumps({'tz': '8'}).encode()))
assert not d.get('error'), d
assert d['stats']['total'] > 1000, d['stats']['total']
assert 0 <= d['score']['closeness'] <= 100
assert d['score'].get('experimental') is not None
assert d.get('forecast') and d['forecast'].get('scenarios'), 'forecast missing: ' + str(d.get('notes'))
assert len(d['images']) >= 5, d['images']
call('/quit', b'')
print('SMOKE OK', d['score']['closeness'], d['score']['band'])
