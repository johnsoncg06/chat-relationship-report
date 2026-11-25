#!/usr/bin/env python3
"""用法: python3 chat_charts.py messages.csv stats.json score.json outdir
產出 PNG 圖表 + charts_summary.json。需要 pandas, numpy, scipy, matplotlib。"""
import sys, os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from scipy import stats as sps

csv_path, stats_path, score_path, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
df = pd.read_csv(csv_path, parse_dates=['ts']); S = json.load(open(stats_path)); SC = json.load(open(score_path))
people = list(S['people'])[:2] if not S['is_group'] else list(S['people'])[:6]
names = {f.name for f in fm.fontManager.ttflist}
font = next((f for f in ['Noto Sans CJK TC', 'Noto Sans CJK SC', 'Noto Sans CJK JP', 'PingFang TC', 'Microsoft JhengHei', 'Heiti TC', 'WenQuanYi Zen Hei', 'Arial Unicode MS'] if f in names), None)
if font: plt.rcParams['font.sans-serif'] = [font]
plt.rcParams['axes.unicode_minus'] = False
L = (lambda zh, en: zh) if font else (lambda zh, en: en)
COL = ['#2a6fdb', '#e8590c', '#2f9e44', '#9c36b5', '#868e96', '#c2255c']
col = {p: COL[i % len(COL)] for i, p in enumerate(people)}
df['month'] = df.ts.dt.to_period('M').astype(str); df['date'] = df.ts.dt.date
summ = {}
def save(fig, name): fig.tight_layout(); fig.savefig(os.path.join(out, name), dpi=140); plt.close(fig)

# 1 每月訊息量（堆疊）
g = df.groupby(['month', 'who']).size().unstack(fill_value=0).reindex(columns=people, fill_value=0)
fig, ax = plt.subplots(figsize=(9, 4)); bottom = np.zeros(len(g))
for p in people: ax.bar(g.index, g[p], bottom=bottom, label=p, color=col[p]); bottom += g[p].values
ax.set_title(L('每月訊息量（依發話者）', 'Monthly message volume')); ax.set_ylabel(L('則數', 'messages')); ax.legend(); plt.xticks(rotation=45)
save(fig, '01_monthly_volume.png')

# 2 每月開話題占比（二人）
first = df.drop_duplicates('session_id')
if not S['is_group'] and len(people) == 2:
    gi = first.groupby(['month', 'who']).size().unstack(fill_value=0).reindex(columns=people, fill_value=0)
    share = gi[people[0]] / gi.sum(axis=1)
    fig, ax = plt.subplots(figsize=(9, 4)); ax.plot(share.index, share.values, marker='o', color=col[people[0]])
    ax.axhline(.5, ls='--', color='gray'); ax.set_ylim(0, 1)
    ax.set_title(L(f'每月「{people[0]}」開話題占比（虛線=50%）', f'Monthly initiation share of {people[0]}')); plt.xticks(rotation=45)
    save(fig, '02_initiation_trend.png')
    summ['initiation_share_by_month'] = {k: round(v, 3) for k, v in share.items()}

# 3 星期×小時熱圖
fig, axes = plt.subplots(1, len(people[:2]), figsize=(11, 3.8), squeeze=False)
wd = L(['一', '二', '三', '四', '五', '六', '日'], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
for ax, p in zip(axes[0], people[:2]):
    d = df[df.who == p]; hm = np.zeros((7, 24))
    for (w, h), c in d.groupby([d.ts.dt.weekday, d.ts.dt.hour]).size().items(): hm[w, h] = c
    im = ax.imshow(hm, aspect='auto', cmap='YlOrRd'); ax.set_yticks(range(7)); ax.set_yticklabels(wd); ax.set_xticks(range(0, 24, 3))
    ax.set_title(f'{p}'); ax.set_xlabel(L('小時', 'hour')); fig.colorbar(im, ax=ax, fraction=.046)
fig.suptitle(L('活躍時段熱圖（星期×小時）', 'Activity heatmap (weekday x hour)')); save(fig, '03_activity_heatmap.png')

# 4 回覆延遲 ECDF（對數軸）
fig, ax = plt.subplots(figsize=(7.5, 4.2)); lat_sum = {}
for p in people:
    v = np.sort(df[(df.who == p)].reply_latency_min.dropna().values)
    if len(v) < 5: continue
    ax.plot(np.maximum(v, .5), np.arange(1, len(v) + 1) / len(v), label=f'{p} (n={len(v)})', color=col[p])
    lat_sum[p] = {'p50': round(float(np.percentile(v, 50)), 1), 'p90': round(float(np.percentile(v, 90)), 1), 'n': int(len(v))}
ax.set_xscale('log'); ax.set_xlabel(L('回覆延遲（分鐘，對數）', 'reply latency (min, log)')); ax.set_ylabel('ECDF')
ax.set_title(L('回覆延遲累積分布', 'Reply latency ECDF')); ax.legend(); ax.grid(alpha=.3); save(fig, '04_reply_latency_ecdf.png')
summ['reply_latency'] = lat_sum
if len(lat_sum) == 2:
    a_, b_ = [df[df.who == p].reply_latency_min.dropna() for p in people[:2]]
    if len(a_) > 5 and len(b_) > 5: u = sps.mannwhitneyu(a_, b_); summ['latency_mannwhitney_p'] = round(float(u.pvalue), 4)

# 5 對話段（session）長度分布
sess = df.groupby('session_id').agg(n=('ts', 'size'), dur=('ts', lambda x: (x.max() - x.min()).total_seconds() / 60))
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
axes[0].hist(sess.n, bins=np.unique(np.logspace(0, np.log10(max(2, sess.n.max())), 25).astype(int)), color='#4263eb'); axes[0].set_xscale('log')
axes[0].set_title(L('每段對話的訊息數', 'Messages per session')); axes[0].set_xlabel(L('則數（對數）', 'messages (log)'))
axes[1].hist(sess.dur.clip(lower=1), bins=np.logspace(0, np.log10(max(10, sess.dur.max())), 25), color='#0ca678'); axes[1].set_xscale('log')
axes[1].set_title(L('每段對話長度', 'Session duration')); axes[1].set_xlabel(L('分鐘（對數）', 'minutes (log)'))
save(fig, '05_session_profile.png'); summ['sessions'] = {'count': int(len(sess)), 'median_msgs': float(sess.n.median()), 'median_min': round(float(sess.dur.median()), 1)}

# 6 關鍵字累積曲線
kws = [(k, L(z, k)) for k, z in [('goodnight', '晚安'), ('miss_you', '想你'), ('love_you', '愛你/喜歡你'), ('pet_name', '暱稱'), ('heart', '愛心表情')] if k in df.columns and df[k].sum() > 0]
if kws:
    fig, axes = plt.subplots(1, len(kws), figsize=(3.6 * len(kws), 3.6), squeeze=False)
    for ax, (k, lab) in zip(axes[0], kws):
        for p in people:
            d = df[(df.who == p) & (df[k] == 1)].sort_values('ts')
            if len(d): ax.step(d.ts, np.arange(1, len(d) + 1), where='post', color=col[p], label=p)
        ax.set_title(lab); ax.tick_params(axis='x', rotation=45); ax.legend(fontsize=7)
    fig.suptitle(L('關鍵詞累積次數', 'Cumulative keyword counts')); save(fig, '06_keyword_cumulative.png')

# 7 每週訊息量與趨勢檢定
wk = df.set_index('ts').resample('W').size()
fig, ax = plt.subplots(figsize=(9, 3.8)); ax.plot(wk.index, wk.values, color='#495057', marker='.')
if len(wk) >= 6:
    x = np.arange(len(wk)); rho, pv = sps.spearmanr(x, wk.values); sl = np.polyfit(x, wk.values, 1)
    ax.plot(wk.index, np.polyval(sl, x), '--', color='#e03131'); summ['weekly_trend'] = {'spearman_rho': round(float(rho), 3), 'p': round(float(pv), 4), 'slope_msgs_per_week': round(float(sl[0]), 2)}
    ax.set_title(L(f'每週訊息量（Spearman ρ={rho:.2f}, p={pv:.3f}）', f'Weekly volume (Spearman rho={rho:.2f}, p={pv:.3f})'))
cp = (S.get('changepoints') or {}).get('volume')
if cp:
    ax.axvline(pd.Timestamp(cp['week_start']), color='#7048e8', ls=':'); ax.text(pd.Timestamp(cp['week_start']), ax.get_ylim()[1] * .92, L(f"變點 p={cp['p_permutation']}", f"changepoint p={cp['p_permutation']}"), color='#7048e8')
    summ['changepoint_volume'] = cp
save(fig, '07_weekly_trend.png')

# 8 訊息長度分布
fig, ax = plt.subplots(figsize=(7, 4))
data = [np.log10(df[(df.who == p) & (df.kind == 'text') & (df.n_chars > 0)].n_chars.values) for p in people]
data = [d for d in data if len(d)]
if data:
    vp = ax.violinplot(data, showmedians=True); ax.set_xticks(range(1, len(data) + 1)); ax.set_xticklabels(people[:len(data)])
    ax.set_ylabel(L('字數（log10）', 'chars (log10)')); ax.set_title(L('訊息長度分布', 'Message length distribution')); save(fig, '08_message_length.png')

# 9 親密度定位圖
fig, ax = plt.subplots(figsize=(6, 5.4))
ax.axvspan(0, 25, color='#f1f3f5'); ax.add_patch(plt.Rectangle((35, 25), 65, 30, color='#fff3bf', alpha=.7)); ax.add_patch(plt.Rectangle((55, 55), 45, 45, color='#ffc9c9', alpha=.7))
ax.add_patch(plt.Rectangle((50, 0), 50, 25, color='#d3f9d8', alpha=.7))
for t, x, y in [(L('點頭之交', 'acquaintance'), 3, 90), (L('好友/兄弟', 'close friend'), 60, 8), (L('曖昧', 'ambiguous'), 60, 38), (L('情侶', 'partners'), 70, 80)]: ax.text(x, y, t, fontsize=10, color='#495057')
ax.scatter([SC['closeness']], [SC['romantic_signal']], s=140, color='#d6336c', zorder=5, edgecolor='k')
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.set_xlabel(L('親密度 closeness', 'closeness')); ax.set_ylabel(L('浪漫訊號 romantic', 'romantic signal'))
ax.set_title(L('關係區間定位（粗略分區，非精確界線）', 'Relationship map (rough regions)')); save(fig, '09_relationship_map.png')

# 10 子分數雷達
dims = SC.get('dimensions') or SC['sub_closeness']
labs = list(dims); vals = list(dims.values()); ang = np.linspace(0, 2 * np.pi, len(labs), endpoint=False)
fig = plt.figure(figsize=(5.4, 5.4)); ax = fig.add_subplot(111, polar=True)
ax.plot(np.r_[ang, ang[0]], np.r_[vals, vals[0]], color='#1c7ed6'); ax.fill(np.r_[ang, ang[0]], np.r_[vals, vals[0]], alpha=.25, color='#1c7ed6')
ax.set_xticks(ang); ax.set_xticklabels(labs if font else [f'd{i+1}' for i in range(len(labs))]); ax.set_ylim(0, 100); ax.set_title(L('五維度（互惠／回應／投入／溫度／穩定）', 'Five dimensions') if SC.get('dimensions') else L('親密度子分數', 'Closeness sub-scores'), pad=14)
save(fig, '10_closeness_radar.png')
json.dump(summ, open(os.path.join(out, 'charts_summary.json'), 'w'), ensure_ascii=False, indent=1)
print(sorted(os.listdir(out)))
