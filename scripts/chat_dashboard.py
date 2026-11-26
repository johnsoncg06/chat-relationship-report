#!/usr/bin/env python3
"""用法: python3 chat_dashboard.py messages.csv stats.json score.json forecast.json outdir
產出 11_forecast.svg、12_scenarios.svg、13_dashboard.svg（一頁總覽，最易讀）與 scorecard.json（所有關鍵數字）。只用標準函式庫。"""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lite as lt
from _svg import Svg, Axes, legend, INK, MUTE

csv_path, stats_path, score_path, fc_path, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
rows = lt.load_csv(csv_path); S = json.load(open(stats_path, encoding='utf-8')); SC = json.load(open(score_path, encoding='utf-8')); F = json.load(open(fc_path, encoding='utf-8'))
if 'error' in F: print(json.dumps(F, ensure_ascii=False)); sys.exit()
people = list(S['people'])[:2]
wd, wn = lt.weekly_counts(rows); H = F['horizon_weeks']
fut = [wd[-1] + dt.timedelta(weeks=h + 1) for h in range(H)]
fc = F['forecast_msgs_per_week']; p10 = [fc[f'+{h+1}w']['p10'] for h in range(H)]; p50 = [fc[f'+{h+1}w']['p50'] for h in range(H)]; p90 = [fc[f'+{h+1}w']['p90'] for h in range(H)]
sc = F['scenarios']; ks = sorted(sc, key=lambda k: sc[k]['point'])
pts = [sc[k]['point'] for k in ks]; lo = [sc[k]['point'] - sc[k]['p10'] for k in ks]; hi = [sc[k]['p90'] - sc[k]['point'] for k in ks]
cpv = (S.get('changepoints') or {}).get('volume')
def ticks(d0, d1, n=6):
    a, b = d0.toordinal(), d1.toordinal(); return [(a + (b - a) * i / (n - 1), dt.date.fromordinal(int(a + (b - a) * i / (n - 1))).isoformat()) for i in range(n)]

def forecast_axes(sv, x, y, w, h, title, labels=True):
    ymx = max(wn + p90 + [1]) * 1.1; ax = Axes(sv, x, y, w, h, (wd[0].toordinal(), fut[-1].toordinal()), (0, ymx), title=title); ax.frame(xticks=ticks(wd[0], fut[-1], 5 if w < 500 else 6))
    sv.poly([(ax.px(d.toordinal()), ax.py(n)) for d, n in zip(wd, wn)], '#495057', 1.8)
    up = [(ax.px(d.toordinal()), ax.py(v)) for d, v in zip(fut, p90)]; dn = [(ax.px(d.toordinal()), ax.py(v)) for d, v in zip(fut, p10)]
    sv.poly(up + dn[::-1], '#1c7ed6', 0, '#1c7ed6', .2, close=True)
    sv.poly([(ax.px(wd[-1].toordinal()), ax.py(wn[-1]))] + [(ax.px(d.toordinal()), ax.py(v)) for d, v in zip(fut, p50)], '#1c7ed6', 2)
    for d, v in zip(fut, p50): sv.circle(ax.px(d.toordinal()), ax.py(v), 3, '#1c7ed6')
    sv.line(ax.px(wd[-1].toordinal()), ax.y, ax.px(wd[-1].toordinal()), ax.y + ax.h, '#868e96', 1, '2 3')
    if cpv:
        cx = ax.px(dt.date.fromisoformat(cpv['week_start'][:10]).toordinal()); sv.line(cx, ax.y, cx, ax.y + ax.h, '#7048e8', 1.4, '2 3')
    return ax

def scen_axes(sv, x, y, w, h, title):
    xmax = max(60, max(sc[k]['p90'] for k in ks) + 8); ax = Axes(sv, x, y, w, h, (0, xmax), (0, len(ks)), title=title); ax.frame(xticks=None, yticks=[], grid=True)
    band = h / len(ks)
    for i, k in enumerate(ks):
        cy = y + h - (i + .5) * band; bh = band * .55
        sv.rect(ax.px(0), cy - bh / 2, ax.px(pts[i]) - ax.px(0), bh, '#e8590c', op=.8)
        sv.line(ax.px(sc[k]['p10']), cy, ax.px(sc[k]['p90']), cy, INK, 1.3)
        for v in (sc[k]['p10'], sc[k]['p90']): sv.line(ax.px(v), cy - 4, ax.px(v), cy + 4, INK, 1.3)
        sv.text(ax.px(sc[k]['p90']) + 6, cy + 4, f'{pts[i]:.0f}%', 11, 'start', INK)
        sv.text(x - 8, cy + 4, k, 11, 'end', INK)
    return ax

# 11 預測扇形圖
sv = Svg(900, 400); forecast_axes(sv, 70, 60, 800, 270, f"未來 {H} 週訊息量情境（淡出風險 {100*F['fade_risk_4wk']:.0f}%）")
legend(sv, 80, 28, [('實際每週訊息量', '#495057'), ('情境中位數', '#1c7ed6'), ('80% 情境區間', '#a5c8f0')]); sv.save(os.path.join(out, '11_forecast.svg'))

# 12 情境可能性（橫條＋誤差線）
sv = Svg(900, 360); ax = scen_axes(sv, 250, 50, 620, 240, '未來關係發展情境')
sv.text(ax.x + ax.w / 2, ax.y + ax.h + 38, '相對可能性 %（啟發式，未校準；誤差線 = 輸入擾動 10–90%）', 11, 'middle', MUTE); sv.save(os.path.join(out, '12_scenarios.svg'))

# 13 一頁總覽
ini = S['initiations']; tot = sum(ini.values()) or 1; latm = S['reply_latency_min_median']
sv = Svg(1200, 800); sv.text(24, 40, '聊天關係總覽', 22, 'start', INK, 'bold')
cards = [('親密度', f"{SC['closeness']}/100"), ('浪漫訊號', f"{SC['romantic_signal']}/100"), ('趨勢', SC['trend']), ('信心', SC['confidence']), ('總訊息', f"{S['total']}")]
for i, (t, v) in enumerate(cards): sv.text(30 + i * 235, 90, v, 26, 'start', '#1c7ed6', 'bold'); sv.text(30 + i * 235, 112, t, 12, 'start', MUTE)
sv.text(24, 140, '區間：' + SC['band'], 13, 'start', INK)
d = SC['dimensions']; ax = Axes(sv, 90, 190, 270, 170, (0, 100), (0, len(d)), title='五維度', tsize=13); ax.frame(xticks=None, yticks=[])
for i, (k, v) in enumerate(d.items()):
    cy = ax.y + ax.h - (i + .5) * ax.h / len(d); sv.rect(ax.px(0), cy - 11, ax.px(v) - ax.px(0), 22, '#2f9e44'); sv.text(ax.px(v) + 5, cy + 4, v, 11); sv.text(ax.x - 6, cy + 4, k, 11, 'end')
forecast_axes(sv, 470, 190, 700, 190, '每週訊息量與未來情境')
scen_axes(sv, 250, 450, 430, 270, '情境相對可能性 %（啟發式）')
ci = S['closeness_inputs']
tbl = [('開話題占比', ' / '.join(f"{100*ini.get(p,0)/tot:.0f}%" for p in people)), ('回覆中位數(分)', ' / '.join(str(latm.get(p, '-')) for p in people)),
       ('晚安日占比', f"{100*ci['goodnight_day_ratio']:.0f}%"), ('深夜佔比', f"{100*ci['late_night_share']:.0f}%"), ('活躍日占比', f"{100*ci['active_day_ratio']:.0f}%"),
       ('最長沈默(天)', str(ci['longest_silence_days'])), ('淡出風險(4週)', f"{100*F['fade_risk_4wk']:.0f}%")]
sv.text(900, 440, f"關鍵數字（{' / '.join(people)}）", 12, 'middle', INK, 'bold')
for i, (k_, v_) in enumerate(tbl): y_ = 475 + i * 34; sv.text(740, y_, k_, 12, 'start', '#495057'); sv.text(1150, y_, v_, 13, 'end', INK, 'bold'); sv.line(740, y_ + 10, 1150, y_ + 10, '#e9ecef', 1)
sv.save(os.path.join(out, '13_dashboard.svg'))

card = {'scores': {k: SC[k] for k in ('closeness', 'romantic_signal', 'band', 'trend', 'confidence', 'romantic_direction')}, 'dimensions': SC['dimensions'],
        'people': people, 'initiation_share_pct': {p: round(100 * ini.get(p, 0) / tot, 1) for p in people}, 'median_reply_min': latm,
        'fade_risk_4wk': F['fade_risk_4wk'], 'scenarios': F['scenarios'], 'advice_rules': F['rule_advice']}
json.dump(card, open(os.path.join(out, 'scorecard.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(sorted(os.listdir(out)))
