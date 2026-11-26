#!/usr/bin/env python3
"""用法: python3 chat_charts.py messages.csv stats.json score.json outdir
產出 SVG 圖表 + charts_summary.json。只用標準函式庫（圖由瀏覽器渲染，中文字型用系統字型）。"""
import sys, os, json, math, datetime as dt
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lite as lt
from _svg import Svg, Axes, legend, ramp, YLORRD, kde, COL, INK, MUTE, nice_ticks

csv_path, stats_path, score_path, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
rows = lt.load_csv(csv_path); S = json.load(open(stats_path, encoding='utf-8')); SC = json.load(open(score_path, encoding='utf-8'))
people = list(S['people'])[:2] if not S['is_group'] else list(S['people'])[:6]
col = {p: COL[i % len(COL)] for i, p in enumerate(people)}
summ = {}
for r in rows: r['month'] = f"{r['ts']:%Y-%m}"
def path(name): return os.path.join(out, name)
def date_ticks(d0, d1, n=6):   # d0,d1: datetime.date / datetime；回傳 [(序數, 標籤)]
    a, b = d0.toordinal(), d1.toordinal(); span = max(1, b - a)
    return [(a + span * i / (n - 1), dt.date.fromordinal(int(a + span * i / (n - 1))).isoformat()) for i in range(n)]

# 1 每月訊息量（堆疊）
months = sorted({r['month'] for r in rows}); cnt = Counter((r['month'], r['who']) for r in rows)
tot = [sum(cnt[(m, p)] for p in people) for m in months]; ymax = max(tot + [1])
sv = Svg(900, 400); ax = Axes(sv, 70, 50, 800, 260, (0, len(months)), (0, ymax * 1.05), title='每月訊息量（依發話者）', ylabel='則數')
ax.frame(xticks=[], yticks=None)
bw = ax.w / max(len(months), 1) * 0.8
for i, m in enumerate(months):
    base = 0; cx = ax.px(i + 0.5)
    for p in people:
        v = cnt[(m, p)]; y1, y0 = ax.py(base + v), ax.py(base); sv.rect(cx - bw / 2, y1, bw, y0 - y1, col[p]); base += v
    sv.text(cx, ax.y + ax.h + 14, m, 10, 'end', MUTE, rot=-45)
legend(sv, 80, 28, [(p, col[p]) for p in people]); sv.save(path('01_monthly_volume.svg'))

# 2 每月開話題占比（二人）
seen = set(); first = []
for r in rows:
    if r['session_id'] not in seen: seen.add(r['session_id']); first.append(r)
if not S['is_group'] and len(people) == 2:
    gi = Counter((r['month'], r['who']) for r in first); share = {}
    for m in months:
        t = sum(gi[(m, p)] for p in people)
        if t: share[m] = gi[(m, people[0])] / t
    ms = list(share); sv = Svg(900, 400); ax = Axes(sv, 70, 50, 800, 260, (0, max(len(ms) - 1, 1)), (0, 1), title=f'每月「{people[0]}」開話題占比（虛線=50%）')
    ax.frame(xticks=[], yticks=[(v, f'{int(v * 100)}%') for v in (0, .25, .5, .75, 1)])
    sv.line(ax.x, ax.py(.5), ax.x + ax.w, ax.py(.5), '#868e96', 1.2, '6 4')
    pts = [(ax.px(i), ax.py(share[m])) for i, m in enumerate(ms)]; sv.poly(pts, col[people[0]], 2)
    for (x_, y_), m in zip(pts, ms): sv.circle(x_, y_, 3.5, col[people[0]]); sv.text(x_, ax.y + ax.h + 14, m, 10, 'end', MUTE, rot=-45)
    sv.save(path('02_initiation_trend.svg')); summ['initiation_share_by_month'] = {k: round(v, 3) for k, v in share.items()}

# 3 星期×小時熱圖
pp = people[:2]; W = 430; sv = Svg(60 + W * len(pp), 360); allhm = {}
for p in pp:
    hm = [[0] * 24 for _ in range(7)]
    for r in rows:
        if r['who'] == p: hm[r['ts'].weekday()][r['ts'].hour] += 1
    allhm[p] = hm
for k, p in enumerate(pp):
    hm = allhm[p]; mx = max(max(row) for row in hm) or 1; x0 = 60 + k * W; y0 = 60; cw, ch = 14.5, 32
    sv.text(x0 + 12 * cw, y0 - 10, p, 13, 'middle', INK, 'bold')
    for w_ in range(7):
        sv.text(x0 - 6, y0 + w_ * ch + ch / 2 + 4, '一二三四五六日'[w_], 11, 'end', MUTE)
        for h_ in range(24): sv.rect(x0 + h_ * cw, y0 + w_ * ch, cw, ch, ramp(hm[w_][h_] / mx, YLORRD))
    for h_ in range(0, 24, 3): sv.text(x0 + h_ * cw + cw / 2, y0 + 7 * ch + 15, h_, 10, 'middle', MUTE)
    sv.text(x0 + 12 * cw, y0 + 7 * ch + 34, f'小時（最深色 = {mx} 則）', 11, 'middle', MUTE)
sv.text(sv.w / 2, 24, '活躍時段熱圖（星期×小時）', 15, 'middle', INK, 'bold'); sv.save(path('03_activity_heatmap.svg'))

# 4 回覆延遲 ECDF（對數軸）
lat = {p: sorted(r['reply_latency_min'] for r in rows if r['who'] == p and r['reply_latency_min'] is not None) for p in people}
lat_sum = {}; ser = []
for p in people:
    v = lat[p]
    if len(v) < 5: continue
    ser.append((p, v)); lat_sum[p] = {'p50': round(lt.percentile(v, 50), 1), 'p90': round(lt.percentile(v, 90), 1), 'n': len(v)}
allv = [max(x, .5) for _, v in ser for x in v] or [1, 10]
lo, hi = 0.5, max(10, max(allv)); sv = Svg(780, 420); ax = Axes(sv, 70, 50, 680, 290, (lo, hi), (0, 1), xs='log', title='回覆延遲累積分布', xlabel='回覆延遲（分鐘，對數）', ylabel='ECDF')
ax.frame(yticks=[(v, f'{v:g}') for v in (0, .25, .5, .75, 1)])
for p, v in ser:
    n = len(v); step = max(1, n // 400); pts = [(ax.px(max(v[i], .5)), ax.py((i + 1) / n)) for i in range(0, n, step)] + [(ax.px(max(v[-1], .5)), ax.py(1))]
    sv.poly(pts, col[p], 2)
legend(sv, 80, 28, [(f'{p} (n={len(v)})', col[p]) for p, v in ser]); sv.save(path('04_reply_latency_ecdf.svg')); summ['reply_latency'] = lat_sum
if len(lat_sum) == 2:
    a_, b_ = lat[people[0]], lat[people[1]]
    if len(a_) > 5 and len(b_) > 5: summ['latency_mannwhitney_p'] = round(lt.mannwhitney_p(a_, b_), 4)

# 5 對話段（session）長度分布
sess = defaultdict(list)
for r in rows: sess[r['session_id']].append(r['ts'])
sn = [len(v) for v in sess.values()]; sd_ = [(max(v) - min(v)).total_seconds() / 60 for v in sess.values()]
def hist(vals, edges):
    c = [0] * (len(edges) - 1)
    for v in vals:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1] or (i == len(edges) - 2 and v == edges[-1]): c[i] += 1; break
    return c
mn_ = max(2, max(sn)); edges_n = sorted({int(10 ** (math.log10(mn_) * i / 24)) for i in range(25)})
md_ = max(10, max(sd_)); edges_d = [10 ** (math.log10(md_) * i / 24) for i in range(25)]
sv = Svg(980, 400)
for k, (vals, edges, ttl, xl, color) in enumerate([(sn, edges_n, '每段對話的訊息數', '則數（對數）', '#4263eb'), ([max(1, v) for v in sd_], edges_d, '每段對話長度', '分鐘（對數）', '#0ca678')]):
    c = hist(vals, edges); fi = next((i for i, n_ in enumerate(c) if n_), 0); lo_ = max(edges[fi], 1e-9) if edges[fi] > 0 else 1
    ax = Axes(sv, 70 + k * 480, 50, 400, 260, (lo_ if lo_ < edges[-1] else 1, edges[-1]), (0, max(c) * 1.1 or 1), xs='log', title=ttl, xlabel=xl); ax.frame()
    for i, n_ in enumerate(c):
        if i < fi: continue
        x1, x2 = ax.px(max(edges[i], 1e-9)), ax.px(edges[i + 1]); sv.rect(x1, ax.py(n_), max(x2 - x1 - 0.5, 0.5), ax.y + ax.h - ax.py(n_), color)
sv.save(path('05_session_profile.svg'))
summ['sessions'] = {'count': len(sess), 'median_msgs': float(lt.median(sn)), 'median_min': round(lt.median(sd_), 1)}

# 6 關鍵字累積曲線
kws = [(k, z) for k, z in [('goodnight', '晚安'), ('miss_you', '想你'), ('love_you', '愛你/喜歡你'), ('pet_name', '暱稱'), ('heart', '愛心表情')] if rows and k in rows[0] and sum(r[k] for r in rows) > 0]
if kws:
    t0, t1 = min(r['ts'] for r in rows), max(r['ts'] for r in rows); sv = Svg(100 + 330 * len(kws), 380)
    for j, (k, lab) in enumerate(kws):
        series = {p: sorted(r['ts'] for r in rows if r['who'] == p and r[k] == 1) for p in people}; ym = max([len(v) for v in series.values()] + [1])
        ax = Axes(sv, 60 + j * 330, 60, 260, 240, (t0.toordinal(), t1.toordinal() + 1), (0, ym * 1.08), title=lab, tsize=13)
        ax.frame(xticks=[(v, l[5:]) for v, l in date_ticks(t0, t1, 3)])
        for p in people:
            v = series[p]
            if not v: continue
            pts = [(ax.px(v[0].toordinal()), ax.py(0))]
            for i, t in enumerate(v): pts += [(ax.px(t.toordinal()), ax.py(i)), (ax.px(t.toordinal()), ax.py(i + 1))]
            pts.append((ax.px(t1.toordinal() + 1), ax.py(len(v)))); sv.poly(pts, col[p], 1.8)
    sv.text(sv.w / 2, 26, '關鍵詞累積次數', 15, 'middle', INK, 'bold'); legend(sv, 70, 350, [(p, col[p]) for p in people]); sv.save(path('06_keyword_cumulative.svg'))

# 7 每週訊息量與趨勢檢定
wd, wn = lt.weekly_counts(rows); x = list(range(len(wn))); sv = Svg(900, 380)
title = '每週訊息量'
trend = None
if len(wn) >= 6:
    rho, pv = lt.spearman(x, wn); sl, ic = lt.polyfit1(x, wn); trend = (sl, ic)
    summ['weekly_trend'] = {'spearman_rho': round(rho, 3), 'p': round(pv, 4), 'slope_msgs_per_week': round(sl, 2)}
    title = f'每週訊息量（Spearman ρ={rho:.2f}, p={pv:.3f}）'
ymx = max(wn + [1]) * 1.12; ax = Axes(sv, 70, 50, 800, 260, (wd[0].toordinal(), wd[-1].toordinal()), (0, ymx), title=title); ax.frame(xticks=[(v, l) for v, l in date_ticks(wd[0], wd[-1], 6)])
sv.poly([(ax.px(d.toordinal()), ax.py(n)) for d, n in zip(wd, wn)], '#495057', 1.8)
if trend: sv.poly([(ax.px(wd[i].toordinal()), ax.py(trend[0] * i + trend[1])) for i in (0, len(wd) - 1)], '#e03131', 1.8, dash='7 4')
cp = (S.get('changepoints') or {}).get('volume')
if cp:
    cx = ax.px(dt.date.fromisoformat(cp['week_start'][:10]).toordinal()); sv.line(cx, ax.y, cx, ax.y + ax.h, '#7048e8', 1.5, '2 3')
    sv.text(cx + 4, ax.y + 14, f"變點 p={cp['p_permutation']}", 11, 'start', '#7048e8'); summ['changepoint_volume'] = cp
sv.save(path('07_weekly_trend.svg'))

# 8 訊息長度分布（小提琴圖）
data = [(p, sorted(math.log10(r['n_chars']) for r in rows if r['who'] == p and r['kind'] == 'text' and r['n_chars'] > 0)) for p in people]
data = [(p, d) for p, d in data if d]
if data:
    sv = Svg(700, 400); gmin = min(d[0] for _, d in data); gmax = max(d[-1] for _, d in data); pad = (gmax - gmin) * .08 + .05
    ax = Axes(sv, 70, 50, 600, 290, (0, len(data)), (gmin - pad, gmax + pad), title='訊息長度分布', ylabel='字數（log10）'); ax.frame(xticks=[], yticks=None)
    gr = [gmin - pad + (gmax - gmin + 2 * pad) * i / 80 for i in range(81)]
    for i, (p, d) in enumerate(data):
        dens = kde(d, gr); dm = max(dens) or 1; cx = ax.px(i + .5); half = ax.w / len(data) * .38; c = col[p]
        pts = [(cx + dens[j] / dm * half, ax.py(g)) for j, g in enumerate(gr)] + [(cx - dens[j] / dm * half, ax.py(g)) for j, g in reversed(list(enumerate(gr)))]
        sv.poly(pts, c, 1.2, c, .35, close=True); md = lt.median(d); sv.line(cx - half * .6, ax.py(md), cx + half * .6, ax.py(md), INK, 2)
        sv.line(cx, ax.py(d[0]), cx, ax.py(d[-1]), INK, 1); sv.text(cx, ax.y + ax.h + 18, p, 12, 'middle', INK)
    sv.save(path('08_message_length.svg'))

# 9 親密度定位圖
sv = Svg(560, 560); ax = Axes(sv, 70, 50, 440, 440, (0, 100), (0, 100), title='關係區間定位（粗略分區，非精確界線）', xlabel='親密度 closeness', ylabel='浪漫訊號 romantic', tsize=13)
ax.frame(grid=False)
for (x0, y0, x1, y1, c) in [(0, 0, 25, 100, '#f1f3f5'), (35, 25, 100, 55, '#fff3bf'), (55, 55, 100, 100, '#ffc9c9'), (50, 0, 100, 25, '#d3f9d8')]:
    sv.rect(ax.px(x0), ax.py(y1), ax.px(x1) - ax.px(x0), ax.py(y0) - ax.py(y1), c, op=.8)
for t, x_, y_ in [('點頭之交', 3, 90), ('好友/兄弟', 60, 8), ('曖昧', 60, 38), ('情侶', 70, 80)]: sv.text(ax.px(x_), ax.py(y_), t, 13, 'start', '#495057')
sv.circle(ax.px(SC['closeness']), ax.py(SC['romantic_signal']), 9, '#d6336c', '#000', 1.2); sv.save(path('09_relationship_map.svg'))

# 10 子分數雷達
dims = SC.get('dimensions') or SC['sub_closeness']; labs = list(dims); vals = list(dims.values()); n = len(labs)
sv = Svg(560, 560); cx, cy, R = 280, 290, 190; sv.text(280, 32, '五維度（互惠／回應／投入／溫度／穩定）' if SC.get('dimensions') else '親密度子分數', 15, 'middle', INK, 'bold')
ang = [-math.pi / 2 + 2 * math.pi * i / n for i in range(n)]
for lvl in (20, 40, 60, 80, 100): sv.poly([(cx + R * lvl / 100 * math.cos(a), cy + R * lvl / 100 * math.sin(a)) for a in ang], '#dee2e6', 1, close=True)
for a, l, v in zip(ang, labs, vals):
    sv.line(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a), '#dee2e6', 1)
    sv.text(cx + (R + 24) * math.cos(a), cy + (R + 24) * math.sin(a) + 4, l, 13, 'middle', INK)
pts = [(cx + R * v / 100 * math.cos(a), cy + R * v / 100 * math.sin(a)) for a, v in zip(ang, vals)]
sv.poly(pts, '#1c7ed6', 2, '#1c7ed6', .25, close=True)
for (x_, y_), v in zip(pts, vals): sv.circle(x_, y_, 3.5, '#1c7ed6'); sv.text(x_, y_ - 8, v, 10, 'middle', '#1864ab')
sv.save(path('10_closeness_radar.svg'))
json.dump(summ, open(os.path.join(out, 'charts_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(sorted(os.listdir(out)))
