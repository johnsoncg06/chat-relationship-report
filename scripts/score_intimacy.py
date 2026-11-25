#!/usr/bin/env python3
"""用法: python3 score_intimacy.py stats.json  -> 親密度/浪漫訊號/五維度/區間/信心"""
import json, sys, statistics as st
d = json.load(open(sys.argv[1]))
if 'error' in d: print(json.dumps(d, ensure_ascii=False)); sys.exit()
ci = d['closeness_inputs']
def lin(x, lo, hi):  # 線性映射到 0-100（錨點為經驗設定，非常模樣本）
    return max(0.0, min(100.0, 100 * (x - lo) / (hi - lo)))
lat = list(d['reply_latency_min_median'].values()) or [120]
rate = lambda k: st.mean(d['per_100_msgs'][p].get(k, 0) for p in d['per_100_msgs']) if 'per_100_msgs' in d else 0
avg_len = st.mean(d['avg_len_chars'].values()) if d['avg_len_chars'] else 0
sub = {
 '聯絡頻率': (25, lin(ci['active_day_ratio'], .1, .9)),
 '互動密度': (15, lin(ci['msgs_per_active_day'], 5, 80)),
 '持續性':   (10, 100 - lin(ci['longest_silence_days'], 2, 30)),
 '晚安儀式': (10, lin(ci['goodnight_day_ratio'], 0, .5)),
 '深夜互動': (10, lin(ci['late_night_share'], 0, .08)),
 '話語長度': (15, lin(avg_len, 3, 25)),
}
LAT_OK = d.get('reply_latency_reliable', True)
if LAT_OK: sub['回覆速度'] = (15, 100 - lin(st.median(lat), 5, 120))
wsum = sum(w for w, v in sub.values())
closeness = sum(w * v for w, v in sub.values()) / wsum   # 回覆速度不可採用時，其餘權重重新正規化
romantic_rate = rate('miss_you') + rate('love_you') + rate('pet_name') + .5 * rate('heart')
ini = list(d['initiations'].values()); share = max(ini) / sum(ini) if ini else .5
rom = {
 '情感詞密度': (50, lin(romantic_rate, 0, 8)),
 '晚安儀式':   (15, lin(ci['goodnight_day_ratio'], 0, .5)),
 '深夜互動':   (15, lin(ci['late_night_share'], 0, .08)),
 '主動對稱':   (10, 100 * (1 - abs(share - .5) * 2)),
 '單人對話':   (10, 0 if d['is_group'] else 100),
}
romantic = sum(w * v for w, v in rom.values()) / 100

# ---- 五維度（0-100）：互惠、回應、投入、溫度、穩定 ----
def balance(dct):
    v = [x for x in dct.values() if x is not None]
    return 100 * (1 - abs(max(v) / sum(v) - .5) * 2) if len(v) == 2 and sum(v) > 0 else None
def bal_rate(dct):
    v = [x['rate_other_responded'] for x in dct.values() if x['rate_other_responded'] is not None]
    return 100 * (1 - abs(v[0] - v[1])) if len(v) == 2 else None
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
dims = None
if not d['is_group']:
    bid_rates = [x['rate_other_responded'] for x in d['bids_by_sender'].values() if x['rate_other_responded'] is not None]
    over2 = list(d['reply_over_2h_share'].values()) or [0.2]
    qrate = st.mean(d['question_marks'].get(p, 0) / d['people'][p] * 100 for p in d['people'])
    warm = lin(rate('miss_you') + rate('love_you') + rate('pet_name') + .5 * rate('heart') + .25 * rate('laugh'), 0, 10)
    dims = {
     '互惠': mean([balance(d['people']), balance(d['initiations']), balance(d['conversation_enders']), bal_rate(d['bids_by_sender'])]),
     '回應': mean([(100 - lin(st.median(lat), 5, 120)) if LAT_OK else None, lin(st.mean(bid_rates), .3, .95) if bid_rates else None, 100 - lin(st.mean(over2), .05, .4)]),
     '投入': mean([lin(ci['msgs_per_active_day'], 5, 80), lin(avg_len, 3, 25), lin(qrate, 2, 15)]),
     '溫度': .6 * warm + .4 * lin(ci['goodnight_day_ratio'], 0, .5),
     '穩定': mean([lin(ci['active_day_ratio'], .1, .9), 100 - lin(ci['longest_silence_days'], 2, 30), 100 - lin(d.get('weekly_volume_cv') or 0, .3, 1.2)]),
    }
    if ci['span_days'] < 14: dims['穩定'] = None   # 不到兩週，穩定度沒有意義
    dims = {k: round(v) for k, v in dims.items() if v is not None}

f, s2 = ci['first_half_msgs_per_active_day'], ci['second_half_msgs_per_active_day']
trend = '升溫' if s2 > f * 1.5 else '降溫' if s2 < f * 0.6 else '持平'
if d['is_group']: band = '群組：不套用關係區間，只看群組熱度'
elif closeness < 25: band = '點頭之交／事務往來'
elif romantic >= 55 and closeness >= 55: band = '情侶／伴侶'
elif romantic >= 25 and closeness >= 35: band = '曖昧～交往初期'
elif closeness >= 50: band = '好友／兄弟姊妹／閨蜜（家人需本人確認）'
else: band = '普通朋友／同學同事'
if not d['is_group'] and (ci['span_days'] < 14 or d.get('top2_days_share', 0) > 0.6): band += '（僅供參考：資料太短或由事件爆量主導）'
asym = None
if not d['is_group'] and 'per_100_msgs' in d:
    r = {p: d['per_100_msgs'][p].get('miss_you', 0) + d['per_100_msgs'][p].get('love_you', 0) + d['per_100_msgs'][p].get('pet_name', 0) for p in d['per_100_msgs']}
    hi, lo = max(r.values()), min(r.values()); asym = '單向偏重' if hi > 0 and lo < hi * .4 else '雙向'
conf_pts = (d['total'] >= 500) + (ci['span_days'] >= 30) + (ci['active_days'] >= 15)
conf = '高' if conf_pts == 3 and d['total'] >= 2000 else '中' if conf_pts >= 2 else '低'
if ci['span_days'] < 14 or d.get('top2_days_share', 0) > 0.6: conf = '低'   # 太短或爆量主導，一律低信心
print(json.dumps({'closeness': round(closeness), 'romantic_signal': round(romantic), 'band': band, 'trend': trend,
  'romantic_direction': asym, 'confidence': conf, 'dimensions': dims, 'warnings': d.get('warnings', []),
  'changepoints': d.get('changepoints'), 'sub_closeness': {k: round(v) for k, (w, v) in sub.items()},
  'sub_romantic': {k: round(v) for k, (w, v) in rom.items()}}, ensure_ascii=False, indent=1))
