#!/usr/bin/env python3
"""用法: python3 anonymize.py in.(json|txt) out mapping.json [--names 暱稱1 暱稱2 ...]
把人名換成 P1/P2…，並遮蔽電話、Email、網址、身分證字號、長數字。對照表只留在本機。"""
import re, sys, json, argparse
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('mapping')
ap.add_argument('--names', nargs='*', default=[]); a = ap.parse_args()
PATS = [(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]'), (r'https?://\S+', '[URL]'), (r'\b[A-Z][12]\d{8}\b', '[ID]'),
        (r'(?:\+?886[- ]?|0)9\d{2}[- ]?\d{3}[- ]?\d{3}', '[PHONE]'), (r'(?<!\d)\d{9,}(?!\d)', '[NUMBER]')]
data = json.load(open(a.src, encoding='utf-8')) if a.src.endswith('.json') else open(a.src, encoding='utf-8').read()
names = list(a.names)
if isinstance(data, list):
    for r in data:
        if r.get('who') and r['who'] not in names: names.append(r['who'])
mp = {n: f'P{i + 1}' for i, n in enumerate(names)}
def clean(t):
    for n in sorted(mp, key=len, reverse=True):
        if len(n) >= 2: t = t.replace(n, mp[n])   # 單字名字只換發話者欄位，避免誤傷一般用字
    for p, rep in PATS: t = re.sub(p, rep, t)
    return t
if isinstance(data, list):
    for r in data:
        r['text'] = clean(r.get('text', '')); r['who'] = mp.get(r.get('who'), r.get('who'))
    json.dump(data, open(a.dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
else: open(a.dst, 'w', encoding='utf-8').write(clean(data))
json.dump(mp, open(a.mapping, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'ok: {len(mp)} names mapped -> {a.dst}')
