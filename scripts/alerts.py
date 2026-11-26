#!/usr/bin/env python3
"""用法: python3 alerts.py messages.csv stats.json score.json [forecast.json] [monthly.json] out_alerts.json
關係「可能突破／可能跌落」的提醒與建議。全部是規則式啟發式（未用台灣資料驗證），列出觸發的證據，讓你自己判斷。只用標準函式庫。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lite as lt

a = [x for x in sys.argv[1:]]; out_path = a.pop()
csv_p, st_p, sc_p = a[:3]; fc_p = a[3] if len(a) > 3 else None; mo_p = a[4] if len(a) > 4 else None
ld = lambda p: json.load(open(p, encoding='utf-8')) if p and os.path.isfile(p) else None
S, SC, F, MO = ld(st_p), ld(sc_p), ld(fc_p), ld(mo_p)
rows = lt.load_csv(csv_p); wd, wn = lt.weekly_counts(rows)
al = []


def add(kind, level, title, ev, adv):
    al.append({'type': kind, 'level': level, 'title': title, 'evidence': ev, 'advice': adv})


FALL_ADV = ['先不要追問「你怎麼不回」，也不要一次補很多則；用一則低壓力、好回的訊息（分享一件今天的小事或一個簡單問題）。',
            '回覆節奏貼近對方的節奏，對方慢你就慢一點，避免秒回造成壓力。',
            '把互動換個形式：一通短語音、一個具體的小邀約，通常比增加文字量有效。',
            '如果連續兩週仍在下降，輕鬆地問「最近是不是比較忙？」給彼此台階，並且接受對方可能真的忙或不想繼續。']
UP_ADV = ['趁熱度在的時候，提出一個具體、低壓力的下一步（時間地點明確的見面或通話），不要停在「有空再約」。',
          '維持目前的節奏，不要因為升溫就突然加碼（例如瞬間訊息量暴增）。',
          '確認升溫是雙方的：看對方是否也主動開話題、回覆是否同樣積極，而不只是你這側。',
          '已經見過面的話，可以自然聊聊彼此對下一步的期待。']

# --- 早期模式 ---
if F and F.get('mode') == 'early':
    e = F.get('early') or {}; rk = e.get('risk_label') or ''; cool, warm = e.get('cool_signals', 0), e.get('warm_signals', 0)
    sig = [f"{x['name']}：{x.get('prior')} → {x.get('recent')}（{x['call']}）" for x in (e.get('signals') or []) if x.get('call') in ('降溫', '升溫')][:5]
    if rk.startswith('高'): add('fall', 'high', '可能正在涼掉（未來 1 週）', [f'降溫訊號 {cool} 項、升溫 {warm} 項'] + sig, FALL_ADV)
    elif rk.startswith('中'): add('fall', 'watch', '有降溫跡象，值得留意', [f'降溫訊號 {cool} 項、升溫 {warm} 項'] + sig, FALL_ADV[:3])
    elif warm >= 3 and warm - cool >= 3: add('breakthrough', 'watch', '最近明顯升溫，可能是推進的好時機', [f'升溫訊號 {warm} 項、降溫 {cool} 項'] + sig, UP_ADV)

# --- 完整模式 ---
if F and F.get('scenarios'):
    fr = F.get('fade_risk_4wk') or 0
    if fr >= .5: add('fall', 'high', '未來 4 週訊息量可能明顯下滑', [f'淡出風險 {round(100 * fr)}%（情境模擬，啟發式）', f"最近 4 週平均 {F.get('recent_4wk_msgs_per_week')} 則／週"], FALL_ADV)
    elif fr >= .3: add('fall', 'watch', '訊息量有下滑的可能', [f'淡出風險 {round(100 * fr)}%'], FALL_ADV[:3])
    sc = F['scenarios']; top = max(sc, key=lambda k: sc[k]['point']); order = ['疏遠／淡出', '普通朋友', '摯友（兄弟／姊妹／閨蜜）', '曖昧／交往初期', '情侶／伴侶']
    band = SC.get('band', '')
    cur = next((i for i, k in enumerate(order) if k.split('／')[0] in band), None)
    if cur is not None and order.index(top) > cur and sc[top]['point'] >= 40:
        add('breakthrough', 'watch', f'情境模擬傾向往「{top}」走', [f"目前區間：{band.split('（')[0]}", f"預測第一名：{top} {round(sc[top]['point'])}%（相對可能性，未校準）"], UP_ADV)
    elif cur is not None and order.index(top) < cur and sc[top]['point'] >= 40:
        add('fall', 'watch', f'情境模擬傾向往「{top}」退', [f"目前區間：{band.split('（')[0]}", f"預測第一名：{top} {round(sc[top]['point'])}%"], FALL_ADV[:3])

# --- 近期量能（所有模式）---
if len(wn) >= 6:
    rec = sum(wn[-2:]) / 2; prev = sum(wn[-6:-2]) / 4
    if prev >= 20 and rec <= .6 * prev and not any(x['type'] == 'fall' and x['level'] == 'high' for x in al):
        add('fall', 'watch', '最近 2 週訊息量比前 4 週少了 4 成以上', [f'最近 2 週平均 {rec:.0f} 則／週，前 4 週平均 {prev:.0f} 則／週'], FALL_ADV[:3])
    if prev >= 20 and rec >= 1.4 * prev: add('breakthrough', 'watch', '最近 2 週訊息量明顯上升', [f'最近 2 週平均 {rec:.0f} 則／週，前 4 週平均 {prev:.0f} 則／週'], UP_ADV)

# --- 月度比較：回覆變慢／一面倒開話題／情感詞升降 ---
ms = [m for m in (MO or {}).get('months', []) if not m.get('partial')]
if len(ms) >= 2:
    c, p = ms[-1], ms[-2]
    for who, v in (c.get('median_reply_min') or {}).items():
        pv = (p.get('median_reply_min') or {}).get(who)
        if pv and v >= 2 * pv and v - pv >= 10: add('fall', 'watch', f'「{who}」這個月回覆明顯變慢', [f'回覆中位數 {pv} → {v} 分鐘（{p["month"]} → {c["month"]}）'], FALL_ADV[:2])
    s1 = c.get('initiation_share_first'); s0 = p.get('initiation_share_first')
    if s1 is not None and s0 is not None and c.get('sessions', 0) >= 8 and (s1 >= .85 or s1 <= .15) and .25 <= s0 <= .75:
        who = (MO['people'] or ['?'])[0] if s1 >= .85 else (MO['people'] + ['?', '?'])[1]
        add('fall', 'watch', f'這個月幾乎都是「{who}」在開話題', [f'開話題占比 {round(100 * s0)}% → {round(100 * s1)}%（以第一位為準）'], ['一方獨撐時，另一方可能只是被動回應；試著等一等，看對方是否會主動開話題，而不是繼續加量。'])
    def rate(m, k): return sum(m['keywords'].get(k, {}).values()) / max(1, m['total']) * 100
    for k, lab in (('miss_you', '「想你」'), ('goodnight', '晚安'), ('heart', '愛心表情')):
        if k in c['keywords'] and c['total'] >= 100 and p['total'] >= 100:
            r0, r1 = rate(p, k), rate(c, k)
            if r0 >= 1 and r1 >= 1.5 * r0 and sum(c['keywords'][k].values()) >= 8: add('breakthrough', 'watch', f'{lab}出現頻率上升', [f'每百則 {r0:.1f} → {r1:.1f} 次（{p["month"]} → {c["month"]}）'], UP_ADV[:3])
            elif r0 >= 2 and r1 <= .5 * r0: add('fall', 'watch', f'{lab}出現頻率下降', [f'每百則 {r0:.1f} → {r1:.1f} 次（{p["month"]} → {c["month"]}）'], FALL_ADV[:3])
order = {'high': 0, 'watch': 1}; al.sort(key=lambda x: (order[x['level']], x['type']))
res = {'alerts': al, 'note': '這些提醒是規則式啟發式，沒有用台灣資料驗證；它們指出「值得看一下」的變化，不是預言，也不代表對方的真實想法。看不到電話、見面與其他管道。'}
json.dump(res, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
