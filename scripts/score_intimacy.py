#!/usr/bin/env python3
"""用法: python3 score_intimacy.py stats.json  -> 親密度/浪漫訊號/五維度/區間/信心"""
import json, sys, os, statistics as st
d = json.load(open(sys.argv[1], encoding='utf-8'))
if 'error' in d: print(json.dumps(d, ensure_ascii=False)); sys.exit()
ci = d['closeness_inputs']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _context as CX
_arg = lambda n: next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == n and i + 1 < len(sys.argv)), None)
CTX = CX.normalize(_arg('--met'), _arg('--stage'), _arg('--breakup'))
def lin(x, lo, hi):  # 線性映射到 0-100（錨點為經驗設定，非常模樣本）
    return max(0.0, min(100.0, 100 * (x - lo) / (hi - lo)))
lat = list(d['reply_latency_min_median'].values()) or [120]
rate = lambda k: st.mean(d['per_100_msgs'][p].get(k, 0) for p in d['per_100_msgs']) if 'per_100_msgs' in d else 0
avg_len = st.mean(d['avg_len_chars'].values()) if d['avg_len_chars'] else 0
LAT_OK = d.get('reply_latency_reliable', True)
# 非文字表達：貼圖、語音訊息、照片占全部訊息的比例（雙方平均）。LINE 貼圖在台灣用量高，純看文字長度會低估這類互動。
# 設計成「替代」而不是「加分」：表達量 = max(文字長度分, 非文字比例分)，所以不用貼圖的人不會被扣分，只有以貼圖代替文字的人不被低估。
NONTEXT = ('sticker', 'voice', 'photo')
nt_share = st.mean(sum(d['kinds'].get(p, {}).get(k, 0) for k in NONTEXT) / max(1, d['people'][p]) for p in d['people']) if d.get('kinds') else 0
RS = d.get('rhythm_similarity')
raw = {   # 子分數 0-100；映射的上下限都是經驗設定，沒有用台灣資料校準
 '聯絡頻率': lin(ci['active_day_ratio'], .1, .9),   # 研究顯示「怎麼傳」比「傳多少」更能預測關係滿意度，頻率只當輔助
 '互動密度': lin(ci['msgs_per_active_day'], 5, 80),
 '持續性':   100 - lin(ci['longest_silence_days'], 2, 30),
 '晚安儀式': lin(ci['goodnight_day_ratio'], 0, .5),
 '深夜互動': lin(ci['late_night_share'], 0, .08),
 '話語長度': lin(avg_len, 3, 25),
}
raw['表達量'] = max(raw['話語長度'], lin(nt_share, 0, .35))
if RS: raw['節奏相似'] = RS['score']   # 雙方長度、連發、活躍時段的相似度（實驗性指標，西方參考）
if LAT_OK: raw['回覆速度'] = 100 - lin(st.median(lat), 5, 120)
# 權重設定檔：base = 先前版本；tw = 依台灣習慣的經驗微調（貼圖用量高 → 話語長度改為「表達量」，貼圖可替代文字；回覆速度的「慢」門檻因人而異 → 權重 15 降為 12）
# 重要：tw 的調整依據是東亞（台、日、港）的問卷／實驗與使用習慣，不是用台灣聊天紀錄加關係結果校準出來的，所以仍標為「未驗證」。
PROFILES = {
 'base': {'聯絡頻率': 12, '互動密度': 15, '持續性': 10, '晚安儀式': 10, '深夜互動': 10, '話語長度': 15, '節奏相似': 13, '回覆速度': 15},
 'tw':   {'聯絡頻率': 12, '互動密度': 15, '持續性': 10, '晚安儀式': 10, '深夜互動': 10, '表達量': 15, '節奏相似': 13, '回覆速度': 12},
}
TIER = {'表達量': '東亞參考', '回覆速度': '東亞參考', '節奏相似': '西方參考（實驗性）'}   # 其餘一律「未驗證」；目前沒有任何指標達到「台灣驗證」
PROFILE = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--profile' and i + 1 < len(sys.argv)), os.environ.get('CHATREL_PROFILE', 'tw'))
if PROFILE not in PROFILES: PROFILE = 'tw'
def closeness_of(name):
    ws = {k: w for k, w in PROFILES[name].items() if k in raw}   # 缺資料（如回覆速度不可採用）時，其餘權重重新正規化
    return sum(w * raw[k] for k, w in ws.items()) / sum(ws.values()), ws
closeness, used_w = closeness_of(PROFILE)
sub = {k: (w, raw[k]) for k, w in used_w.items()}
romantic_rate = rate('miss_you') + rate('love_you') + rate('pet_name') + .5 * rate('heart')
ini = list(d['initiations'].values()); share = max(ini) / sum(ini) if ini else .5
_rw = CX.romantic_weights({'情感詞密度': 50, '晚安儀式': 15, '深夜互動': 15, '主動對稱': 10, '單人對話': 10}, CTX)
rom = {
 '情感詞密度': (_rw['情感詞密度'], lin(romantic_rate, 0, 8)),
 '晚安儀式':   (_rw['晚安儀式'], lin(ci['goodnight_day_ratio'], 0, .5)),
 '深夜互動':   (_rw['深夜互動'], lin(ci['late_night_share'], 0, .08)),
 '主動對稱':   (_rw['主動對稱'], 100 * (1 - abs(share - .5) * 2)),
 '單人對話':   (_rw['單人對話'], 0 if d['is_group'] else 100),
}
romantic = sum(w * v for w, v in rom.values()) / sum(w for w, v in rom.values())   # 未改權重時分母就是 100

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
     '投入': mean([lin(ci['msgs_per_active_day'], 5, 80), raw['表達量'] if PROFILE == 'tw' else raw['話語長度'], lin(qrate, 2, 15)]),
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
if not d['is_group'] and (ci['span_days'] < 14 or d.get('top2_days_share', 0) > 0.6 or d.get('structured_chat', {}).get('flag')): band += '（僅供參考：資料太短或由事件爆量主導）'
asym = None
if not d['is_group'] and 'per_100_msgs' in d:
    r = {p: d['per_100_msgs'][p].get('miss_you', 0) + d['per_100_msgs'][p].get('love_you', 0) + d['per_100_msgs'][p].get('pet_name', 0) for p in d['per_100_msgs']}
    hi, lo = max(r.values()), min(r.values()); asym = '單向偏重' if hi > 0 and lo < hi * .4 else '雙向'
STRUCT = bool(d.get('structured_chat', {}).get('flag'))
conf_pts = (d['total'] >= 500) + (ci['span_days'] >= 30) + (ci['active_days'] >= 15)
conf = '高' if conf_pts == 3 and d['total'] >= 2000 else '中' if conf_pts >= 2 else '低'
if ci['span_days'] < 14 or d.get('top2_days_share', 0) > 0.6 or STRUCT: conf = '低'   # 太短或爆量主導，一律低信心
CTXO = CX.describe(CTX, d['is_group'])
if CTXO: conf = CX.lower_confidence(conf, CTX)
print(json.dumps({'closeness': round(closeness), 'romantic_signal': round(romantic), 'band': band, 'trend': trend,
  'romantic_direction': asym, 'confidence': conf, 'dimensions': dims, 'warnings': d.get('warnings', []),
  'changepoints': d.get('changepoints'),
  'experimental': {'style_matching': d.get('style_matching'), 'we_talk': d.get('we_talk'), 'rhythm_similarity': RS, 'note': '實驗性：研究多為英語情侶；華語效度未驗證，不納入親密度，只供參考。' + ('此情境（有人剛失戀）下語言類指標不可靠，請勿解讀。' if CTXO and CTXO.get('breakup') else '')},
  'context': CTXO,
  'structured_chat': d.get('structured_chat'), 'evidence': d.get('evidence'), 'sub_closeness': {k: round(v) for k, (w, v) in sub.items()},
  'profile': PROFILE, 'weights': used_w, 'evidence_levels': {k: TIER.get(k, '未驗證') for k in used_w},
  'closeness_by_profile': {n: round(closeness_of(n)[0]) for n in PROFILES},
  'weights_note': '權重為經驗設定；tw 版依東亞（台、日、港）使用習慣微調，沒有任何指標經台灣聊天紀錄加關係結果驗證。',
  'sub_romantic': {k: round(v) for k, (w, v) in rom.items()}}, ensure_ascii=False, indent=1))
