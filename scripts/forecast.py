#!/usr/bin/env python3
"""用法: python3 forecast.py messages.csv stats.json score.json > forecast.json
未來走勢（情境模擬）＋各種關係的相對可能性＋規則式建議。
重要：沒有「真實關係結果」的標註資料可校準，所以輸出是【啟發式情境分數】，不是真正的機率。
可能性是用手設權重的 softmax 加上輸入擾動得到區間；解讀時只看排序與區間寬度，不當成預言。"""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lite as lt

csv_path, stats_path, score_path = sys.argv[1:4]
rows = lt.load_csv(csv_path); S = json.load(open(stats_path, encoding='utf-8')); SC = json.load(open(score_path, encoding='utf-8'))
rng = random.Random(0); nrng = random.Random(1)
if S.get('is_group') or 'error' in S or not SC.get('dimensions'):
    print(json.dumps({'error': 'only_for_two_person_chats'}, ensure_ascii=False)); sys.exit()

_, wk_n = lt.weekly_counts(rows)
y = [math.log1p(v) for v in wk_n]; n = len(y)
H = 8
out = {'weeks_observed': int(n), 'horizon_weeks': H, 'mode': 'standard'}

# ---- 早期模式：曖昧期很容易在一兩週內涼掉，8 週太長；只看最近 7 天 vs 前 7 天，加上 7 天的量能推估 ----
import datetime as _dt
CTXO = SC.get('context') or {}
EARLY_MET = {'online_blind_date', 'street', 'matchmaking', 'family', 'friend', 'new'}
early_ctx = CTXO.get('met') in EARLY_MET or str(CTXO.get('stage') or '').startswith('not_met')
def early_block():
    ds = sorted({r['ts'].date() for r in rows}); first, last = ds[0], ds[-1]; span = (last - first).days + 1
    if span < 10 or len(ds) < 7: return None
    win = min(7, span // 2)
    r0 = last - _dt.timedelta(days=win - 1); p0 = r0 - _dt.timedelta(days=win)
    rec = [r for r in rows if r['ts'].date() >= r0]; pri = [r for r in rows if p0 <= r['ts'].date() < r0]
    day = lambda xs: len({r['ts'].date() for r in xs})
    med = lambda v: lt.median(v) if v else None
    def lat(xs): return [r['reply_latency_min'] for r in xs if r['reply_latency_min'] is not None]
    def starters(xs):
        seen, c = set(), {}
        for r in xs:
            if r['session_id'] in seen: continue
            seen.add(r['session_id']); c[r['who']] = c.get(r['who'], 0) + 1
        return c
    sig = []
    def add(name, kind, recent, prior, call, note=''): sig.append({'name': name, 'kind': kind, 'recent': recent, 'prior': prior, 'call': call, 'note': note})
    # 1 訊息量
    a, b = len(rec) / win, len(pri) / win
    add('每日訊息量', '行為', round(a, 1), round(b, 1), '降溫' if a < .5 * b else '升溫' if a > 1.5 * b else '持平')
    # 2 有聊天的天數
    a, b = day(rec) / win, day(pri) / win
    add('有聊天的天數比例', '行為', round(a, 2), round(b, 2), '降溫' if b > 0 and a < .6 * b else '升溫' if b > 0 and a > 1.4 * b else '持平')
    # 3 回覆速度（分鐘中位數）
    lr, lp = lat(rec), lat(pri)
    if S.get('reply_latency_reliable', True) and len(lr) >= 8 and len(lp) >= 8:
        a, b = med(lr), med(lp)
        add('回覆速度（中位數，分鐘）', '行為', round(a, 1), round(b, 1), '降溫' if a - b >= 15 and a > 2 * b else '升溫' if b - a >= 15 and a < .5 * b else '持平')
    else: add('回覆速度（中位數，分鐘）', '行為', None, None, '資料不足', '回覆樣本不足或不可採用')
    # 4 誰在開話題
    sr, sp = starters(rec), starters(pri); nr = sum(sr.values())
    if nr >= 4:
        top = max(sr.values()) / nr; topp = (max(sp.values()) / sum(sp.values())) if sp else None
        add('開話題是否一面倒（最多的人占比）', '行為', round(top, 2), round(topp, 2) if topp is not None else None, '降溫' if top >= .85 else '升溫' if top <= .65 else '持平', '一方獨撐的話，另一方可能只是被動回應')
    else: add('開話題是否一面倒（最多的人占比）', '行為', None, None, '資料不足', '最近開話題次數少於 4')
    # 5 訊息長度（逐人，取下降最多的人）
    worst = None
    for who in S['people']:
        cr = [r['n_chars'] for r in rec if r['who'] == who and r['kind'] == 'text']; cp = [r['n_chars'] for r in pri if r['who'] == who and r['kind'] == 'text']
        if len(cr) >= 8 and len(cp) >= 8 and med(cp) > 0:
            ratio = med(cr) / med(cp)
            if worst is None or ratio < worst[0]: worst = (ratio, who, med(cr), med(cp))
    if worst: add('訊息長度（變短最多的人）', '行為', worst[2], worst[3], '降溫' if worst[0] < .6 else '升溫' if worst[0] > 1.3 else '持平', f'指「{worst[1]}」')
    else: add('訊息長度（變短最多的人）', '行為', None, None, '資料不足', '文字訊息太少')
    # 6 晚安
    gr, gp = sum(r.get('goodnight', 0) for r in rec), sum(r.get('goodnight', 0) for r in pri)
    add('互道晚安次數', '內容', gr, gp, '降溫' if gp >= 2 and gr == 0 else '升溫' if gr >= 2 and gr > gp else '持平')
    # 7 邀約與延後（關鍵字比對）
    ir, dr = sum(r.get('invite', 0) for r in rec), sum(r.get('defer', 0) for r in rec)
    ip, dp = sum(r.get('invite', 0) for r in pri), sum(r.get('defer', 0) for r in pri)
    add('邀約／延後婉拒用語（最近）', '內容', f'邀約 {ir}・延後 {dr}', f'邀約 {ip}・延後 {dp}', '降溫' if dr >= 2 and dr > ir else '升溫' if ir >= 1 and dr == 0 else '持平', '關鍵字比對，請對照證據片段自己讀')
    valid = [x for x in sig if x['call'] != '資料不足']
    cool = sum(1 for x in valid if x['call'] == '降溫'); warm = sum(1 for x in valid if x['call'] == '升溫'); net = cool - warm
    label = '資料不足以判斷' if len(valid) < 4 else '高' if net >= 3 else '中' if net >= 1 else '低'
    # 7 天量能推估：最近 14 天（不足則全部）每日訊息量，衰減趨勢 + 殘差重抽樣
    dc = {}
    for r in rows: dc[r['ts'].date()] = dc.get(r['ts'].date(), 0) + 1
    k_ = min(14, span); series = [dc.get(last - _dt.timedelta(days=k_ - 1 - i), 0) for i in range(k_)]
    yy_ = [math.log1p(v) for v in series]; b_, a_ = lt.polyfit1(list(range(k_)), yy_); res_ = [v - (a_ + b_ * i) for i, v in enumerate(yy_)]
    recent_mean = lt.mean(series[-7:]); fades = 0; R = 600; fut = []
    for _ in range(R):
        lvl = lt.mean(yy_[-3:]); sl = b_; row_ = []
        for h in range(7):
            sl *= .8; lvl += sl; row_.append(math.expm1(max(0.0, lvl + nrng.choice(res_))))
        fut.append(row_); fades += lt.mean(row_) < .3 * max(recent_mean, 1)
    fade7 = fades / R; fm = [lt.mean(p) for p in fut]
    bump = ''
    if fade7 >= .5 and label in ('低', '中'): label = {'低': '中', '中': '高'}[label]; bump = '（量能推估偏低，已上調一級）'
    cav = [f'樣本很小：最近 {win} 天 {len(rec)} 則、前 {win} 天 {len(pri)} 則，只能看到短期變化', '降溫訊號越多越值得注意，單一訊號（例如剛好考試週）不要過度解讀',
           '訊號門檻是經驗設定，沒有用台灣資料校準；邀約／延後是關鍵字比對，請對照證據片段']
    cav += list(CTXO.get('forecast_caveats') or [])
    return {'window_days': win, 'span_days': span, 'risk_label': label + bump if label != '資料不足以判斷' else label, 'cool_signals': cool, 'warm_signals': warm, 'signals': sig,
            'projection': {'horizon_days': 7, 'recent_7d_msgs_per_day': round(recent_mean, 1), 'next_7d_msgs_per_day': {'p10': round(lt.percentile(fm, 10), 1), 'p50': round(lt.percentile(fm, 50), 1), 'p90': round(lt.percentile(fm, 90), 1)}, 'fade_risk_7d': round(fade7, 3)},
            'caveats': cav, 'rule': '降溫訊號數減升溫訊號數：≥3 高、≥1 中、其餘低；有效訊號少於 4 個則不判斷；7 天量能推估淡出機率 ≥50% 時上調一級。'}
EB = early_block() if (n < 8 or early_ctx) else None
if n < 8:
    if EB is None:
        print(json.dumps({'error': 'need_more_data', 'weeks': int(n)}, ensure_ascii=False)); sys.exit()
    out.update({'mode': 'early', 'early': EB, 'evidence_strength': '弱', 'caveats': EB['caveats']})
    print(json.dumps(out, ensure_ascii=False, indent=1)); sys.exit()
if EB: out['early'] = EB

# ---- 1. 未來訊息量：近 k 週線性趨勢 + 衰減（damped）+ 殘差重抽樣 ----
k = min(12, n); x = list(range(k)); yy = y[-k:]
b, a0 = lt.polyfit1(x, yy); res = [v - (a0 + b * i) for i, v in enumerate(yy)]; sd = lt.std(res, ddof=2) if k > 3 else 0.3
def simulate(slope, phi=0.85, reps=600):
    paths = []
    for r in range(reps):
        lvl = lt.mean(yy[-3:]); s = slope; row = []
        for h in range(H):
            s *= phi; lvl += s
            row.append(math.expm1(max(0.0, lvl + nrng.choice(res) * 1.0)))
        paths.append(row)
    return paths
P = simulate(b)
col = lambda h: [p[h] for p in P]
recent = lt.mean([math.expm1(v) for v in yy[-4:]])
out['recent_4wk_msgs_per_week'] = round(recent, 1)
out['forecast_msgs_per_week'] = {f'+{h+1}w': {'p10': round(lt.percentile(col(h), 10), 1), 'p50': round(lt.percentile(col(h), 50), 1), 'p90': round(lt.percentile(col(h), 90), 1)} for h in range(H)}
out['trend_slope_pct_per_week'] = round(100 * (math.exp(b) - 1), 1)
# 淡出風險：未來 4 週平均量 < 近期的 30%
fade = lt.mean([1.0 if lt.mean(p[:4]) < 0.3 * max(recent, 1) else 0.0 for p in P])
growth = math.log((lt.mean([v for p in P for v in p[:8]]) + 1) / (recent + 1))
out['fade_risk_4wk'] = round(fade, 3); out['log_growth_ratio'] = round(growth, 3)
hist = [math.expm1(v) for v in (y[:-8] if n >= 16 else y[:max(1, n // 2)])]
drop = min(1.0, max(0.0, 1 - recent / max(lt.median(hist), 1)))   # 近期量相對先前常態掉了多少（已發生的下滑）
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
    ks = list(L); v = [L[k_] / 1.6 for k_ in ks]   # 溫度 1.6：刻意壓平，避免假精確
    m_ = max(v); e_ = [math.exp(t - m_) for t in v]; z_ = sum(e_)
    return dict(zip(ks, [t / z_ for t in e_]))
asym = 1.0 if SC.get('romantic_direction') == '單向偏重' else 0.0
trend_up = {'升溫': 1.0, '持平': 0.0, '降溫': -1.0}.get(SC['trend'], 0.0)
base = scenario_probs(SC['closeness'], SC['romantic_signal'], growth, fade, D['回應'], trend_up, asym, drop)
draws = {k_: [] for k_ in base}
for _ in range(400):   # 輸入不確定度：分數 ±8、成長 ±0.25、淡出 ±0.1
    clip = lambda v_, lo_, hi_: min(hi_, max(lo_, v_))
    d_ = scenario_probs(clip(SC['closeness'] + rng.gauss(0, 8), 0, 100), clip(SC['romantic_signal'] + rng.gauss(0, 8), 0, 100),
                        growth + rng.gauss(0, .25), clip(fade + rng.gauss(0, .1), 0, 1), D['回應'], trend_up, asym, drop)
    for k_, v_ in d_.items(): draws[k_].append(v_)
out['scenarios'] = {k_: {'point': round(100 * base[k_], 1), 'p10': round(100 * lt.percentile(draws[k_], 10), 1), 'p90': round(100 * lt.percentile(draws[k_], 90), 1)} for k_ in base}
out['current_band_scenario'] = cur_key
out['stay_probability_pct'] = out['scenarios'][cur_key]['point'] if cur_key else None   # 「維持目前關係」= 落在目前區間的相對可能性
out['scenario_note'] = '情境名稱是「未來 8 週最可能落在哪個區間」，目前所處區間已加慣性。手設權重的 softmax，未用真實關係結果校準；可能性之和為 100%，只代表「在這五種落點裡，目前資料偏向哪一邊」。文字看不出性別與血緣：兄弟／姊妹／閨蜜／哥們統稱摯友，家人關係需本人確認，不在預測範圍。'

# 證據強度：越短、越由事件或規則帶動，區間越不可信；這裡只標示，不改數字
caveats = []
if S.get('closeness_inputs', {}).get('span_days', 0) < 56: caveats.append('資料不足 8 週，走勢與落點只供參考')
if S.get('structured_chat', {}).get('flag'): caveats.append('疑似結構化對話（輪流發問等），互動量由規則帶動')
if S.get('top2_days_share', 0) > 0.6: caveats.append('訊息集中在少數幾天，近期水位不代表日常')
for c in ((SC.get('context') or {}).get('forecast_caveats') or []): caveats.append(c)
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
