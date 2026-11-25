#!/usr/bin/env python3
"""用法: python3 coding_stats.py sample.json passA.json passB.json
sample.json: [{id, who, text}]；passA/passB: [{id, code}]，code 為 pos / neg / neu。
輸出：正負比、Wilson 95% 信賴區間、兩次編碼的一致性（Cohen's kappa）。kappa < 0.6 就不要下結論。"""
import sys, json
from math import sqrt
from collections import Counter
smp = {r['id']: r for r in json.load(open(sys.argv[1]))}
A = {r['id']: r['code'] for r in json.load(open(sys.argv[2]))}
B = {r['id']: r['code'] for r in json.load(open(sys.argv[3]))}
ids = [i for i in smp if i in A and i in B]
def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); w = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - w) / d, 3), round((c + w) / d, 3)]
cats = ['pos', 'neg', 'neu']; n = len(ids)
agree = sum(A[i] == B[i] for i in ids) / n if n else 0
pa = Counter(A[i] for i in ids); pb = Counter(B[i] for i in ids)
pe = sum((pa[c] / n) * (pb[c] / n) for c in cats) if n else 0
kappa = (agree - pe) / (1 - pe) if n and pe < 1 else 1.0
# 兩次編碼不一致的訊息視為 neu，避免把不確定的判斷算進正負比
final = {i: (A[i] if A[i] == B[i] else 'neu') for i in ids}
def summarize(sel):
    c = Counter(final[i] for i in sel); pos, neg = c['pos'], c['neg']
    return {'n': len(sel), 'pos': pos, 'neg': neg, 'neu': c['neu'], 'pos_to_neg': round(pos / neg, 2) if neg else None,
            'pos_share_of_nonneutral': round(pos / (pos + neg), 3) if pos + neg else None, 'wilson95': wilson(pos, pos + neg)}
out = {'coded': n, 'percent_agreement': round(agree, 3), 'cohens_kappa': round(kappa, 3),
       'reliable': kappa >= 0.6 and n >= 40, 'overall': summarize(ids),
       'by_speaker': {w: summarize([i for i in ids if smp[i]['who'] == w]) for w in sorted({smp[i]['who'] for i in ids})}}
print(json.dumps(out, ensure_ascii=False, indent=1))
