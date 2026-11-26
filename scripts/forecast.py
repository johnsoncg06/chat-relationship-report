#!/usr/bin/env python3
"""用法: python3 forecast.py messages.csv stats.json score.json > forecast.json
未來走勢（情境模擬）＋各種關係的相對可能性＋規則式建議。
重要：沒有「真實關係結果」的標註資料可校準，所以輸出是【啟發式情境分數】，不是真正的機率。
可能性是用手設權重的 softmax 加上輸入擾動得到區間；解讀時只看排序與區間寬度，不當成預言。"""
import sys, json, math, random
import numpy as np, pandas as pd

csv_path, stats_path, score_path = sys.argv[1:4]
df = pd.read_csv(csv_path, parse_dates=['ts']); S = json.load(open(stats_path, encoding='utf-8')); SC = json.load(open(score_path, encoding='utf-8'))
rng = random.Random(0); nrng = np.random.default_rng(0)
if S.get('is_group') or 'error' in S or not SC.get('dimensions'):
    print(json.dumps({'error': 'only_for_two_person_chats'}, ensure_ascii=False)); sys.exit()

wk = df.set_index('ts').resample('W').size()
y = np.log1p(wk.values.astype(float)); n = len(y)
H = 8
out = {'weeks_observed': int(n), 'horizon_weeks': H}
if n < 8:
    print(json.dumps({'error': 'need_8_weeks', 'weeks': int(n)}, ensure_ascii=False)); sys.exit()

# ---- 1. 未來訊息量：近 k 週線性趨勢 + 衰減（damped）+ 殘差重抽樣 ----
k = min(12, n); x = np.arange(k); yy = y[-k:]
b, a0 = np.polyfit(x, yy, 1); res = yy - (a0 + b * x); sd = float(res.std(ddof=2)) if k > 3 else 0.3
def simulate(slope, phi=0.85, reps=600):
    paths = np.zeros((reps, H))
    for r in range(reps):
        lvl = yy[-3:].mean(); s = slope
        for h in range(H):
            s *= phi; lvl += s
            paths[r, h] = max(0.0, lvl + nrng.choice(res) * 1.0)
    return np.expm1(paths)
P = simulate(b)
recent = float(np.expm1(yy[-4:]).mean())
out['recent_4wk_msgs_per_week'] = round(recent, 1)
out['forecast_msgs_per_week'] = {f'+{h+1}w': {'p10': round(float(np.percentile(P[:, h], 10)), 1), 'p50': round(float(np.percentile(P[:, h], 50)), 1), 'p90': round(float(np.percentile(P[:, h], 90)), 1)} for h in range(H)}
out['trend_slope_pct_per_week'] = round(100 * (math.exp(b) - 1), 1)
# 淡出風險：未來 4 週平均量 < 近期的 30%
fade = float(np.mean(P[:, :4].mean(axis=1) < 0.3 * max(recent, 1)))
growth = float(np.log((P[:, :8].mean() + 1) / (recent + 1)))
out['fade_risk_4wk'] = round(fade, 3); out['log_growth_ratio'] = round(growth, 3)
hist = np.expm1(y[:-8]) if n >= 16 else np.expm1(y[:max(1, n // 2)])
drop = float(np.clip(1 - recent / max(float(np.median(hist)), 1), 0, 1))   # 近期量相對先前常態掉了多少（已發生的下滑）
out['drop_vs_earlier'] = round(drop, 3)
out['forecast_note'] = '情境模擬：假設趨勢逐週衰減（phi=0.85）、殘差沿用近期波動；不含任何外部事件（考試、搬家、新對象）。'

# ---- 2. 各種關係的相對可能性（啟發式，非校準機率）----
D = SC['dimensions']
BANDMAP = {'情侶': '情侶／伴侶', '曖昧': '曖昧／交往初期', '普通': '普通朋友', '好友': '摯友（兄弟／姊妹／閨蜜）', '點頭': '疏遠／淡出'}   # 順序：普通 先於 好友
cur_key = next((v for k, v in BANDMAP.items() if k in SC['band']), None)
def scenario_probs(c, r, g, f, rec, trend_up, asym, drop=0.0):
    c, r = c / 100, r / 100
    # 五個互斥的「未來 8 週落點」，機率和為 100%；落點 = 目前區間 + 慣性
    L = {
     '疏遠／淡出': 3.2 * f + 2.0 * (1 - c) - 1.2 * g - 0.8 * (rec / 100) + 3.0 * drop,
     '普通朋友': 1.2 - 3.0 * abs(c - 0.4) - 1.0 * r - 1.0 * drop,
     '摯友（兄弟／姊妹／閨蜜）': 2.6 * c - 2.6 * r + 0.4 * g + 0.4 * (rec / 100) - 1.0 * f - 1.5 * drop - 0.6,
     '曖昧／交往初期': 2.8 * r + 0.6 * c + 1.5 * max(g, 0) + 0.6 * trend_up - 0.8 * asym - 1.2 * f - 2.5 * drop,
     '情侶／伴侶': 3.0 * r * c + 1.2 * max(g, 0) + 0.8 * (rec / 100) - 1.5 * asym - 1.5 * f - 0.6 - 2.5 * drop,
    }
    if cur_key: L[cur_key] += 1.6   # 現在所處的區間有慣性：多數關係短期內不會換區間
    ks = list(L); v = np.array([L[k_] for k_ in ks]) / 1.6   # 溫度 1.6：刻意壓平，避免假精確
    p = np.exp(v - v.max()); p /= p.sum()
    return dict(zip(ks, p))
asym = 1.0 if SC.get('romantic_direction') == '單向偏重' else 0.0
trend_up = {'升溫': 1.0, '持平': 0.0, '降溫': -1.0}.get(SC['trend'], 0.0)
base = scenario_probs(SC['closeness'], SC['romantic_signal'], growth, fade, D['回應'], trend_up, asym, drop)
draws = {k_: [] for k_ in base}
for _ in range(400):   # 輸入不確定度：分數 ±8、成長 ±0.25、淡出 ±0.1
    d_ = scenario_probs(np.clip(SC['closeness'] + rng.gauss(0, 8), 0, 100), np.clip(SC['romantic_signal'] + rng.gauss(0, 8), 0, 100),
                        growth + rng.gauss(0, .25), float(np.clip(fade + rng.gauss(0, .1), 0, 1)), D['回應'], trend_up, asym, drop)
    for k_, v_ in d_.items(): draws[k_].append(v_)
out['scenarios'] = {k_: {'point': round(100 * base[k_], 1), 'p10': round(100 * float(np.percentile(draws[k_], 10)), 1), 'p90': round(100 * float(np.percentile(draws[k_], 90)), 1)} for k_ in base}
out['current_band_scenario'] = cur_key
out['stay_probability_pct'] = out['scenarios'][cur_key]['point'] if cur_key else None   # 「維持目前關係」= 落在目前區間的相對可能性
out['scenario_note'] = '情境名稱是「未來 8 週最可能落在哪個區間」，目前所處區間已加慣性。手設權重的 softmax，未用真實關係結果校準；可能性之和為 100%，只代表「在這五種落點裡，目前資料偏向哪一邊」。文字看不出性別與血緣：兄弟／姊妹／閨蜜／哥們統稱摯友，家人關係需本人確認，不在預測範圍。'

# 證據強度：越短、越由事件或規則帶動，區間越不可信；這裡只標示，不改數字
caveats = []
if S.get('closeness_inputs', {}).get('span_days', 0) < 56: caveats.append('資料不足 8 週，走勢與落點只供參考')
if S.get('structured_chat', {}).get('flag'): caveats.append('疑似結構化對話（輪流發問等），互動量由規則帶動')
if S.get('top2_days_share', 0) > 0.6: caveats.append('訊息集中在少數幾天，近期水位不代表日常')
out['evidence_strength'] = '弱' if caveats else '一般'
out['caveats'] = caveats
out['scenario_note'] += ' 研究也顯示，用聊天內容預測關係走向的證據有限（例如以承諾程度為主的模型，分手預測的平衡準確率僅約六成），請把這裡當成討論材料，不是預測。'

# ---- 3. 規則式現況建議（只依資料，不替使用者決定）----
adv = []
dim_sorted = sorted(D.items(), key=lambda kv: kv[1])
ini = S.get('initiations', {}); tot = sum(ini.values()) or 1
for who, v in ini.items():
    if v / tot > 0.7: adv.append(f'「{who}」開話題占 {100*v/tot:.0f}%，主動明顯偏一方（此為行為描述，不代表誰不在乎）。')
tail = S.get('unanswered_tail_sessions', {})
for who, v in tail.items():
    if v >= 5: adv.append(f'「{who}」有 {v} 段對話以連發兩則以上收尾而無人回，可留意是否有被晾著的感受。')
lo = dim_sorted[0]; hi = dim_sorted[-1]
adv.append(f'五維度最弱：{lo[0]} {lo[1]}；最強：{hi[0]} {hi[1]}。')
if drop > 0.5: adv.append(f'近 4 週訊息量比先前常態少了約 {100*drop:.0f}%：整段平均的親密度／浪漫分數可能高估現況，請用 --since 只算近 8–12 週重新評分。')
if SC['trend'] == '降溫': adv.append('前後半段互動量下降明顯：先確認是否有外部原因（考試、忙碌）再解讀。')
if fade > 0.3: adv.append(f'模擬顯示未來 4 週明顯淡出的機率約 {100*fade:.0f}%（情境模擬，非預言）。')
out['rule_advice'] = adv
print(json.dumps(out, ensure_ascii=False, indent=1))
