#!/usr/bin/env python3
"""用法: python3 chat_dashboard.py messages.csv stats.json score.json forecast.json outdir
產出 11_forecast.png、12_scenarios.png、13_dashboard.png（一頁總覽，最易讀）與 scorecard.json（所有關鍵數字）。"""
import sys, os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

csv_path, stats_path, score_path, fc_path, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
df = pd.read_csv(csv_path, parse_dates=['ts']); S = json.load(open(stats_path)); SC = json.load(open(score_path)); F = json.load(open(fc_path))
if 'error' in F: print(json.dumps(F, ensure_ascii=False)); sys.exit()
names = {f.name for f in fm.fontManager.ttflist}
font = next((f for f in ['Noto Sans CJK TC', 'Noto Sans CJK SC', 'Noto Sans CJK JP', 'PingFang TC', 'Microsoft JhengHei', 'Heiti TC', 'WenQuanYi Zen Hei', 'Arial Unicode MS'] if f in names), None)
if font: plt.rcParams['font.sans-serif'] = [font]
plt.rcParams['axes.unicode_minus'] = False
L = (lambda zh, en: zh) if font else (lambda zh, en: en)
EN = {'疏遠／淡出': 'fade out', '普通朋友': 'casual friends', '摯友（兄弟／姊妹／閨蜜）': 'close friends/siblings-like', '曖昧／交往初期': 'ambiguous', '情侶／伴侶': 'partners'}
lab = lambda k: k if font else EN.get(k, k)
people = list(S['people'])[:2]
wk = df.set_index('ts').resample('W').size()
H = F['horizon_weeks']; fut_idx = pd.date_range(wk.index[-1] + pd.Timedelta(weeks=1), periods=H, freq='W')
fc = F['forecast_msgs_per_week']; p10 = [fc[f'+{h+1}w']['p10'] for h in range(H)]; p50 = [fc[f'+{h+1}w']['p50'] for h in range(H)]; p90 = [fc[f'+{h+1}w']['p90'] for h in range(H)]
def save(fig, name): fig.tight_layout(); fig.savefig(os.path.join(out, name), dpi=140); plt.close(fig)

# 11 預測扇形圖
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(wk.index, wk.values, color='#495057', marker='.', label=L('實際每週訊息量', 'actual'))
ax.plot(fut_idx, p50, color='#1c7ed6', marker='o', label=L('情境中位數', 'median'))
ax.fill_between(fut_idx, p10, p90, color='#1c7ed6', alpha=.2, label=L('80% 情境區間', '80% band'))
ax.axvline(wk.index[-1], ls=':', color='gray')
ax.set_title(L(f"未來 {H} 週訊息量情境（淡出風險 {100*F['fade_risk_4wk']:.0f}%）", f"{H}-week volume scenario (fade risk {100*F['fade_risk_4wk']:.0f}%)")); ax.legend(); ax.grid(alpha=.3)
save(fig, '11_forecast.png')

# 12 情境可能性（橫條＋誤差線）
sc = F['scenarios']; ks = sorted(sc, key=lambda k: sc[k]['point'])
fig, ax = plt.subplots(figsize=(8, 3.8))
pts = [sc[k]['point'] for k in ks]; lo = [sc[k]['point'] - sc[k]['p10'] for k in ks]; hi = [sc[k]['p90'] - sc[k]['point'] for k in ks]
ax.barh([lab(k) for k in ks], pts, xerr=[lo, hi], color='#e8590c', alpha=.8, capsize=3)
for i, v in enumerate(pts): ax.text(v + 1, i + .25, f'{v:.0f}%', fontsize=9)
ax.set_xlim(0, max(60, max(sc[k]['p90'] for k in ks) + 8)); ax.set_xlabel(L('相對可能性 %（啟發式，未校準；誤差線 = 輸入擾動 10–90%）', 'relative likelihood % (heuristic, uncalibrated)'))
ax.set_title(L('未來關係發展情境', 'Relationship scenarios')); save(fig, '12_scenarios.png')

# 13 一頁總覽
fig = plt.figure(figsize=(12, 8)); gs = fig.add_gridspec(3, 3, height_ratios=[.9, 1.4, 1.4])
ax = fig.add_subplot(gs[0, :]); ax.axis('off')
ax.text(0, .85, L('聊天關係總覽', 'Chat relationship dashboard'), fontsize=18, weight='bold')
cards = [(L('親密度', 'closeness'), f"{SC['closeness']}/100"), (L('浪漫訊號', 'romantic'), f"{SC['romantic_signal']}/100"), (L('趨勢', 'trend'), SC['trend'] if font else '-'), (L('信心', 'confidence'), SC['confidence'] if font else '-'), (L('總訊息', 'messages'), f"{S['total']}")]
for i, (t, v) in enumerate(cards):
    ax.text(.02 + i * .2, .35, v, fontsize=20, weight='bold', color='#1c7ed6'); ax.text(.02 + i * .2, .08, t, fontsize=10, color='#495057')
ax.text(0, -.2, (L('區間：', 'band: ') + SC['band']) if font else 'band: see report', fontsize=11)
a1 = fig.add_subplot(gs[1, 0]); d = SC['dimensions']; a1.barh(list(d) if font else [f'd{i+1}' for i in range(len(d))], list(d.values()), color='#2f9e44')
a1.set_xlim(0, 100); a1.set_title(L('五維度', 'Five dimensions'))
for i, v in enumerate(d.values()): a1.text(v + 1, i, str(v), va='center')
a2 = fig.add_subplot(gs[1, 1:]); a2.plot(wk.index, wk.values, color='#495057', marker='.'); a2.plot(fut_idx, p50, color='#1c7ed6', marker='o'); a2.fill_between(fut_idx, p10, p90, color='#1c7ed6', alpha=.2)
cpv = (S.get('changepoints') or {}).get('volume')
if cpv: a2.axvline(pd.Timestamp(cpv['week_start']), color='#7048e8', ls=':')
a2.set_title(L('每週訊息量與未來情境', 'Weekly volume + forecast')); a2.grid(alpha=.3)
a3 = fig.add_subplot(gs[2, :2]); a3.barh([lab(k) for k in ks], pts, xerr=[lo, hi], color='#e8590c', alpha=.8, capsize=3); a3.set_title(L('情境相對可能性 %（啟發式）', 'Scenario likelihood % (heuristic)'))
a4 = fig.add_subplot(gs[2, 2]); a4.axis('off')
ini = S['initiations']; tot = sum(ini.values()) or 1; lat = S['reply_latency_min_median']
rows = [(L('開話題占比', 'initiation share'), ' / '.join(f"{100*ini.get(p,0)/tot:.0f}%" for p in people)),
        (L('回覆中位數(分)', 'median reply (min)'), ' / '.join(str(lat.get(p, '-')) for p in people)),
        (L('晚安日占比', 'goodnight days'), f"{100*S['closeness_inputs']['goodnight_day_ratio']:.0f}%"),
        (L('深夜佔比', 'late-night share'), f"{100*S['closeness_inputs']['late_night_share']:.0f}%"),
        (L('活躍日占比', 'active days'), f"{100*S['closeness_inputs']['active_day_ratio']:.0f}%"),
        (L('最長沈默(天)', 'longest silence'), str(S['closeness_inputs']['longest_silence_days'])),
        (L('淡出風險(4週)', 'fade risk 4w'), f"{100*F['fade_risk_4wk']:.0f}%")]
for i, (k_, v_) in enumerate(rows): a4.text(0, .95 - i * .13, k_, fontsize=10, color='#495057'); a4.text(.98, .95 - i * .13, v_, fontsize=10, weight='bold', ha='right')
a4.set_title(L(f"關鍵數字（{' / '.join(people)}）", 'key numbers'), fontsize=10)
save(fig, '13_dashboard.png')

card = {'scores': {k: SC[k] for k in ('closeness', 'romantic_signal', 'band', 'trend', 'confidence', 'romantic_direction')}, 'dimensions': SC['dimensions'],
        'people': people, 'initiation_share_pct': {p: round(100 * ini.get(p, 0) / tot, 1) for p in people}, 'median_reply_min': lat,
        'fade_risk_4wk': F['fade_risk_4wk'], 'scenarios': F['scenarios'], 'advice_rules': F['rule_advice']}
json.dump(card, open(os.path.join(out, 'scorecard.json'), 'w'), ensure_ascii=False, indent=1)
print(sorted(os.listdir(out)))
