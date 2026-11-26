#!/usr/bin/env python3
"""用法: python3 monthly_recap.py messages.csv out_monthly.json
Spotify Wrapped 風格的「月度回顧」：每個月一組數字（全部由程式從訊息時間與標記算出，不讀訊息內容）。只用標準函式庫。"""
import sys, os, json, datetime as dt
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lite as lt

csv_path, out_path = sys.argv[1:3]
rows = lt.load_csv(csv_path)
if not rows: json.dump({'months': [], 'people': []}, open(out_path, 'w', encoding='utf-8')); sys.exit()
people = [p for p, _ in Counter(r['who'] for r in rows).most_common(2)]
WD = '一二三四五六日'
by = defaultdict(list)
for r in rows: by[f"{r['ts']:%Y-%m}"].append(r)
seen = set(); first = []
for r in rows:
    if r['session_id'] not in seen: seen.add(r['session_id']); first.append(r)
ini = defaultdict(Counter)
for r in first: ini[f"{r['ts']:%Y-%m}"][r['who']] += 1


def streak(days):
    best = cur = 0; prev = None
    for d in sorted(days):
        cur = cur + 1 if prev is not None and (d - prev).days == 1 else 1; best = max(best, cur); prev = d
    return best


months = []
for m in sorted(by):
    rs = by[m]; cnt = Counter(r['who'] for r in rs); days = {r['ts'].date() for r in rs}
    perday = Counter(r['ts'].date() for r in rs); bd, bn = perday.most_common(1)[0]
    hours = Counter(r['ts'].hour for r in rs); wds = Counter(r['ts'].weekday() for r in rs)
    late = sum(v for h, v in hours.items() if h < 5) / len(rs)
    lat = {p: [r['reply_latency_min'] for r in rs if r['who'] == p and r['reply_latency_min'] is not None] for p in people}
    kw = {k: {p: sum(r.get(k, 0) for r in rs if r['who'] == p) for p in people} for k in ('goodnight', 'miss_you', 'love_you', 'heart', 'laugh') if rs and k in rs[0]}
    it = ini[m]; itn = sum(it.values())
    y, mo = int(m[:4]), int(m[5:]); nxt = dt.date(y + (mo == 12), mo % 12 + 1, 1); dim = (nxt - dt.date(y, mo, 1)).days
    months.append({'month': m, 'total': len(rs), 'msgs': {p: cnt.get(p, 0) for p in people}, 'active_days': len(days), 'days_in_month': dim, 'streak': streak(days),
                   'busiest_day': {'date': bd.isoformat(), 'n': bn}, 'peak_hour': hours.most_common(1)[0][0], 'peak_weekday': WD[wds.most_common(1)[0][0]], 'late_night_share': round(late, 3),
                   'hours': [hours.get(h, 0) for h in range(24)], 'weekdays': [wds.get(i, 0) for i in range(7)],
                   'median_reply_min': {p: round(lt.median(v), 1) for p, v in lat.items() if len(v) >= 5}, 'keywords': kw,
                   'initiations': {p: it.get(p, 0) for p in people}, 'initiation_share_first': round(it.get(people[0], 0) / itn, 3) if itn else None, 'sessions': itn,
                   'partial': (rs[0]['ts'].date() > dt.date(y, mo, 3)) or (rs[-1]['ts'].date() < nxt - dt.timedelta(days=4))})
for i, c in enumerate(months):
    pv = months[i - 1] if i else None
    c['vs_prev_pct'] = round(100 * (c['total'] / pv['total'] - 1)) if pv and pv['total'] else None
    gn = sum(c['keywords'].get('goodnight', {}).values()); mi = sum(c['keywords'].get('miss_you', {}).values())
    lats = list(c['median_reply_min'].values()); fast = (sum(lats) / len(lats)) if lats else None
    if c['vs_prev_pct'] is not None and c['vs_prev_pct'] >= 50 and not c['partial']: t = ('話癆月', '訊息量比上個月多了一半以上')
    elif c['vs_prev_pct'] is not None and c['vs_prev_pct'] <= -40 and not c['partial']: t = ('安靜月', '訊息量比上個月少了四成以上')
    elif c['late_night_share'] >= .15: t = ('夜貓月', '凌晨 0–5 點的訊息占 %d%%' % round(100 * c['late_night_share']))
    elif gn >= 15: t = ('晚安常客', '這個月說了 %d 次晚安' % gn)
    elif mi >= 10: t = ('想念月', '「想你」出現了 %d 次' % mi)
    elif fast is not None and fast <= 3: t = ('秒回月', '雙方回覆中位數平均 %.1f 分鐘' % fast)
    elif c['active_days'] >= .9 * c['days_in_month']: t = ('天天見面月', '幾乎每天都有聊')
    else: t = ('穩穩聊', '節奏平穩，沒有特別極端的地方')
    c['title'], c['title_why'] = t
json.dump({'people': people, 'months': months, 'note': '全部由訊息時間與關鍵字標記統計；不含訊息內容。資料不完整的月份會標星號。'}, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
