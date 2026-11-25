#!/usr/bin/env python3
"""LINE(.txt) / Instagram(.json 或資料夾) 聊天統計。
用法: python3 chat_stats.py <檔案或資料夾...> [--me 名字] [--gap 6] [--tz 8] > stats.json"""
import re, os, sys, json, glob, random, argparse, statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import comb

DATE_RE = re.compile(r'^(\d{4})[/.\-年](\d{1,2})[/.\-月](\d{1,2})')
MSG_RE = re.compile(r'^(上午|下午|AM|PM)?\s?(\d{1,2}):(\d{2})\s?(AM|PM)?\t([^\t]+)\t(.*)$')
SYS_RE = re.compile(r'^(上午|下午|AM|PM)?\s?\d{1,2}:\d{2}\s?(AM|PM)?\t')
LINE_KIND = [('sticker', r'^\[?(貼圖|Sticker)\]?$'), ('photo', r'^\[?(照片|Photo)\]?$'), ('video', r'^\[?(影片|Video)\]?$'),
             ('voice', r'^\[?(語音訊息|Voice message)\]?$'), ('file', r'^\[?(檔案|File)\]?$'),
             ('call', r'^☎|通話時間|未接來電|Call duration|Missed call'), ('unsent', r'收回了訊息|unsent a message|訊息已收回')]
LEX = {
 'goodnight': r'晚安|good ?night|\bgn\b|早點睡|去睡了|先睡了',
 'miss_you': r'想你|想妳|miss you|好想見',
 'love_you': r'愛你|愛妳|love you|喜歡你|喜歡妳',
 'sorry': r'抱歉|對不起|不好意思|sorry|我的錯',
 'laugh': r'哈哈|XD|www|笑死|lol|😂|🤣',
 'pet_name': r'寶貝|寶寶|親愛的|老公|老婆|\bbb\b|babe|honey|甜心',
 'heart': r'❤|💕|💖|😘|🥰|💗|😍',
}
NEG = re.compile(r'(不|沒|別|才不|不會|不要|不想)\s*$')

def classify(text):
    for k, pat in LINE_KIND:
        if re.search(pat, text.strip(), re.I): return k
    return 'text'

def parse_line(path):
    msgs, cur_date, last = [], None, None
    for raw in open(path, encoding='utf-8-sig', errors='ignore'):
        line = raw.rstrip('\n').rstrip('\r')
        d = DATE_RE.match(line)
        if d and '\t' not in line:
            cur_date = datetime(int(d[1]), int(d[2]), int(d[3])); continue
        m = MSG_RE.match(line)
        if m and cur_date:
            ap1, h, mi, ap2, name, text = m.groups(); h = int(h); ap = ap1 or ap2
            if ap in ('下午', 'PM') and h < 12: h += 12
            if ap in ('上午', 'AM') and h == 12: h = 0
            text = text.strip('"')
            last = {'t': cur_date.replace(hour=h, minute=int(mi)), 'who': name, 'text': text, 'kind': classify(text)}
            msgs.append(last); continue
        if SYS_RE.match(line): last = None; continue   # 系統行（入群、通話摘要等）
        if last and line.strip(): last['text'] += '\n' + line.strip('"')   # 多行訊息
    return msgs

def fix(s):  # IG 匯出把 UTF-8 當 latin-1 存，需還原
    if not isinstance(s, str): return s
    try: return s.encode('latin-1').decode('utf-8')
    except Exception: return s

def parse_ig(path, tz):
    data = json.load(open(path, encoding='utf-8'))
    out = []
    for m in data.get('messages', []):
        t = datetime.fromtimestamp(m['timestamp_ms'] / 1000, timezone(timedelta(hours=tz))).replace(tzinfo=None)
        who = fix(m.get('sender_name', '?')); text = fix(m.get('content', '') or '')
        if m.get('is_unsent'): kind = 'unsent'
        elif 'share' in m: kind = 'share'; text = text or fix(m['share'].get('link', ''))   # 分享貼文/Reels
        elif 'audio_files' in m: kind = 'voice'
        elif 'photos' in m: kind = 'photo'
        elif 'videos' in m: kind = 'video'
        elif 'sticker' in m: kind = 'sticker'
        elif 'call_duration' in m: kind = 'call'
        elif re.search(r'^(.+ )?(liked a message|reacted .* to your message)', text) or text.endswith('to your message'): kind = 'reaction_notice'
        else: kind = 'text'
        if kind == 'reaction_notice': continue
        rec = {'t': t, 'who': who, 'text': text, 'kind': kind}
        out.append(rec)
        for r in m.get('reactions', []) or []:   # 表情回應
            out.append({'t': t, 'who': fix(r.get('actor', '?')), 'text': fix(r.get('reaction', '')), 'kind': 'reaction', 'react_to': who})
    return out

def load(paths, tz):
    files = []
    for p in paths:
        if os.path.isdir(p): files += sorted(glob.glob(os.path.join(p, '**', '*.json'), recursive=True)) + sorted(glob.glob(os.path.join(p, '**', '*.txt'), recursive=True))
        else: files.append(p)
    msgs, src = [], set()
    for f in files:
        if f.endswith('.json'):
            try: msgs += parse_ig(f, tz); src.add('instagram')
            except Exception: pass
        else:
            msgs += parse_line(f); src.add('line')
    msgs.sort(key=lambda m: m['t'])
    return msgs, sorted(src), files

def binom_p(a, b):
    n, k = a + b, min(a, b)
    if n == 0: return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('paths', nargs='+'); ap.add_argument('--gap', type=float, default=6)
    ap.add_argument('--me'); ap.add_argument('--tz', type=float, default=8); ap.add_argument('--export-csv')
    ap.add_argument('--since'); ap.add_argument('--until'); ap.add_argument('--exclude', action='append', default=[], help='排除機器人／系統帳號，可重複'); ap.add_argument('--sample-out'); ap.add_argument('--sample-n', type=int, default=80)
    ap.add_argument('--alias', action='append', default=[], help='合併名字，例: --alias "IG名=LINE名"'); a = ap.parse_args()
    AL = dict(x.split('=', 1) for x in a.alias)
    ALL, src, files = load(a.paths, a.tz)
    for m in ALL:
        m['who'] = AL.get(m['who'], m['who'])
        if 'react_to' in m: m['react_to'] = AL.get(m['react_to'], m['react_to'])
    if a.since: ALL = [m for m in ALL if m['t'].date() >= datetime.fromisoformat(a.since).date()]   # 只分析某段期間（例如變點前後各跑一次）
    if a.until: ALL = [m for m in ALL if m['t'].date() < datetime.fromisoformat(a.until).date()]
    R = [m for m in ALL if m['kind'] == 'reaction']
    M = [m for m in ALL if m['kind'] not in ('reaction', 'unsent')]   # 收回的訊息不計入互動
    if len(M) < 50: print(json.dumps({'error': 'too_few_messages', 'n': len(M), 'files': files}, ensure_ascii=False)); return
    # ---- 排除機器人／系統帳號：手動 --exclude，或自動（兩位以上主要發言者存在時，訊息數 < max(5, 2%) 的發言者）----
    cnt0 = Counter(m['who'] for m in M); BOT = re.compile(r'機器人|bot\b|官方|客服|小幫手|助理|LINE\s?Pay|Official', re.I)
    major = [p for p, c in cnt0.items() if c >= max(5, 0.02 * len(M))]
    excl = set(a.exclude) | ({p for p in cnt0 if p not in major or (BOT.search(p) and cnt0[p] < 0.05 * len(M))} if len(major) >= 2 else set())
    out_excl = {p: cnt0[p] for p in excl if p in cnt0}
    ALL = [m for m in ALL if m['who'] not in excl]; R = [m for m in R if m['who'] not in excl]; M = [m for m in M if m['who'] not in excl]
    if len(M) < 50: print(json.dumps({'error': 'too_few_messages', 'n': len(M), 'excluded': out_excl}, ensure_ascii=False)); return
    people = Counter(m['who'] for m in M)
    P = [p for p, _ in people.most_common()]
    out = {'source': src, 'files': len(files), 'total': len(M), 'span': [str(M[0]['t']), str(M[-1]['t'])],
           'people': dict(people), 'is_group': len(P) > 2, 'me': a.me, 'excluded_senders': out_excl,
           'kinds': {p: dict(Counter(m['kind'] for m in M if m['who'] == p)) for p in P},
           'unsent': dict(Counter(m['who'] for m in ALL if m['kind'] == 'unsent')),
           'reactions_given': dict(Counter(m['who'] for m in R)),
           'shares_sent': dict(Counter(m['who'] for m in M if m['kind'] == 'share'))}
    T = [m for m in M if m['kind'] == 'text']   # 文字統計只看純文字
    if a.export_csv:   # 逐則明細（不含文字內容），給 pandas / BI 使用
        import csv
        rxs = {k: re.compile(p, re.I) for k, p in LEX.items()}
        def flag(k, m):
            if m['kind'] != 'text': return 0
            mm = rxs[k].search(m['text'])
            return int(bool(mm) and not NEG.search(m['text'][:mm.start()]))
        sid, prev = 0, None
        with open(a.export_csv, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh); w.writerow(['ts', 'who', 'kind', 'n_chars', 'session_id', 'reply_latency_min'] + list(LEX))
            for m in M:
                if prev is None or m['t'] - prev['t'] >= timedelta(hours=a.gap): sid += 1
                lat_ = ''
                if prev and prev['who'] != m['who']:
                    dt = (m['t'] - prev['t']).total_seconds() / 60
                    if dt < 720: lat_ = round(dt, 1)
                w.writerow([m['t'].isoformat(sep=' '), m['who'], m['kind'], len(m['text']), sid, lat_] + [flag(k, m) for k in LEX])
                prev = m

    def initiations(gap):
        c, ends = Counter(), Counter(); prev = None
        for m in M:
            if prev is None or m['t'] - prev['t'] >= timedelta(hours=gap):
                c[m['who']] += 1
                if prev: ends[prev['who']] += 1
            prev = m
        return c, ends
    ini, ends = initiations(a.gap)
    out['initiations'] = dict(ini); out['conversation_enders'] = dict(ends)
    out['initiation_sensitivity'] = {f'{g}h': dict(initiations(g)[0]) for g in (3, 6, 12)}

    lat = defaultdict(list); dbl = Counter(); prev = None
    for m in M:
        if prev and prev['who'] != m['who']:
            dt = (m['t'] - prev['t']).total_seconds() / 60
            if dt < 12 * 60: lat[m['who']].append(dt)
        elif prev and prev['who'] == m['who'] and (m['t'] - prev['t']).total_seconds() < 600:
            dbl[m['who']] += 1
        prev = m
    out['reply_latency_min_median'] = {p: round(st.median(v), 1) for p, v in lat.items() if v}
    out['double_text_10min'] = dict(dbl)
    allv = [x for v in lat.values() for x in v]
    zero_share = sum(1 for x in allv if x < 1) / len(allv) if allv else 1.0
    out['reply_latency_zero_share'] = round(zero_share, 3)
    out['reply_latency_reliable'] = bool(allv) and st.median(allv) >= 1 and zero_share < 0.5   # 分鐘解析度＋逐行傳送時，同一分鐘內的來回會讓中位數變 0，不可採用
    out['avg_len_chars'] = {p: round(st.mean(min(len(m['text']), 100) for m in T if m['who'] == p), 1) for p in P if any(m['who'] == p for m in T)}   # 單則最多算 100 字，避免長公告灌高
    out['median_len_chars'] = {p: st.median(len(m['text']) for m in T if m['who'] == p) for p in P if any(m['who'] == p for m in T)}
    out['late_night_00_05_msgs'] = dict(Counter(m['who'] for m in M if m['t'].hour < 5))
    out['question_marks'] = dict(Counter(m['who'] for m in T for _ in re.findall(r'[?？]', m['text'])))

    kw = {}
    for k, pat in LEX.items():
        rx = re.compile(pat, re.I); cnt = Counter(); ex = defaultdict(list); first = {}; firsts = Counter(); seen = set()
        for m in T:
            mm = rx.search(m['text'])
            if not mm or NEG.search(m['text'][:mm.start()]): continue
            cnt[m['who']] += 1; first.setdefault(m['who'], str(m['t']))
            if m['t'].date() not in seen: seen.add(m['t'].date()); firsts[m['who']] += 1
            if len(ex[m['who']]) < 4: ex[m['who']].append(f"{m['t']:%Y-%m-%d %H:%M} {m['text'][:60]}")
        v = sorted(firsts.values(), reverse=True) + [0, 0]
        kw[k] = {'count': dict(cnt), 'first_each_day': dict(firsts), 'first_ever': first,
                 'p_value_first_each_day': round(binom_p(v[0], v[1]), 4) if len(P) == 2 else None, 'examples': dict(ex)}
    out['keywords'] = kw
    if len(P) == 2:
        x, y = ini.get(P[0], 0), ini.get(P[1], 0); out['initiation_p_value'] = round(binom_p(x, y), 4)
        out['per_100_msgs'] = {p: {k: round(100 * kw[k]['count'].get(p, 0) / people[p], 2) for k in kw} for p in P}

    by = defaultdict(lambda: defaultdict(int)); ini_m = defaultdict(Counter); prev = None
    for m in M:
        key = f"{m['t']:%Y-%m}"; by[key][m['who']] += 1
        if prev is None or m['t'] - prev['t'] >= timedelta(hours=a.gap): ini_m[key][m['who']] += 1
        prev = m
    out['monthly'] = {k: {'msgs': dict(by[k]), 'initiations': dict(ini_m[k])} for k in sorted(by)}
    days = sorted({m['t'].date() for m in M}); span = (days[-1] - days[0]).days + 1
    gaps = [(days[i + 1] - days[i]).days for i in range(len(days) - 1)]
    gn = {m['t'].date() for m in T if re.search(LEX['goodnight'], m['text'], re.I)}
    mid = M[0]['t'] + (M[-1]['t'] - M[0]['t']) / 2
    h1 = [m for m in M if m['t'] < mid]; h2 = [m for m in M if m['t'] >= mid]
    per_day = lambda L: round(len(L) / max(1, len({m['t'].date() for m in L})), 1)
    out['closeness_inputs'] = {
        'span_days': span, 'active_days': len(days), 'active_day_ratio': round(len(days) / span, 3),
        'msgs_per_active_day': round(len(M) / len(days), 1), 'longest_silence_days': max(gaps) if gaps else 0,
        'goodnight_day_ratio': round(len(gn) / len(days), 3),
        'late_night_share': round(sum(1 for m in M if m['t'].hour < 5) / len(M), 3),
        'first_half_msgs_per_active_day': per_day(h1), 'second_half_msgs_per_active_day': per_day(h2)}

    # ---- 進階指標：邀約回應、沉默、變點、抽樣 ----
    bids, answered = Counter(), Counter()
    for i, m in enumerate(M):
        if not ((m['kind'] == 'text' and re.search(r'[?？]', m['text'])) or m['kind'] in ('share', 'photo')): continue
        bids[m['who']] += 1
        for n in M[i + 1:i + 8]:
            if n['t'] - m['t'] > timedelta(minutes=30): break
            if n['who'] != m['who']: answered[m['who']] += 1; break
    out['bids_by_sender'] = {p: {'sent': bids[p], 'answered_within_30min': answered[p],
                                 'rate_other_responded': round(answered[p] / bids[p], 3) if bids[p] else None} for p in P}
    sessions, cur = [], []
    for m in M:
        if cur and m['t'] - cur[-1]['t'] >= timedelta(hours=a.gap): sessions.append(cur); cur = []
        cur.append(m)
    sessions.append(cur); tail = Counter()
    for s_ in sessions:
        k = 0
        for m in reversed(s_):
            if m['who'] == s_[-1]['who']: k += 1
            else: break
        if k >= 2 and len({m['who'] for m in s_}) > 1: tail[s_[-1]['who']] += 1   # 連發兩則以上後沒人回的對話段
    out['unanswered_tail_sessions'] = dict(tail)
    out['reply_over_2h_share'] = {p: round(sum(1 for x in v if x > 120) / len(v), 3) for p, v in lat.items() if v}

    def best_split(y, minseg=4):
        def best(v):
            n = len(v); S, Q = [0.0], [0.0]
            for x in v: S.append(S[-1] + x); Q.append(Q[-1] + x * x)
            sse = lambda i, j: (Q[j] - Q[i]) - (S[j] - S[i]) ** 2 / (j - i)
            tot = sse(0, n)
            if tot <= 1e-12: return None, 0.0
            bk, bs = None, tot
            for k in range(minseg, n - minseg + 1):
                s2 = sse(0, k) + sse(k, n)
                if s2 < bs: bk, bs = k, s2
            return bk, 1 - bs / tot
        if len(y) < 2 * minseg + 2: return None
        k, red = best(y)
        if k is None: return None
        rng = random.Random(0); ge = sum(1 for _ in range(300) if best(rng.sample(y, len(y)))[1] >= red)
        return k, red, (ge + 1) / 301
    d0 = M[0]['t'].date(); nweeks = (M[-1]['t'].date() - d0).days // 7 + 1
    wc = [0] * nweeks
    for m in M: wc[(m['t'].date() - d0).days // 7] += 1
    import math
    cps = {}
    r = best_split([math.log1p(x) for x in wc])
    if r:
        k, red, pp = r; cps['volume'] = {'week_start': str(d0 + timedelta(weeks=k)), 'variance_reduction': round(red, 3), 'p_permutation': round(pp, 4),
                                          'before_msgs_per_week': round(sum(wc[:k]) / k, 1), 'after_msgs_per_week': round(sum(wc[k:]) / (nweeks - k), 1)}
    wl = defaultdict(list); prev = None
    for m in M:
        if prev and prev['who'] != m['who']:
            dt = (m['t'] - prev['t']).total_seconds() / 60
            if dt < 720: wl[(m['t'].date() - d0).days // 7].append(dt)
        prev = m
    wks = sorted(w for w, v in wl.items() if len(v) >= 5)
    r = best_split([math.log(st.median(wl[w]) + 1) for w in wks])
    if r:
        k, red, pp = r; cps['reply_latency'] = {'week_start': str(d0 + timedelta(weeks=wks[k])), 'variance_reduction': round(red, 3), 'p_permutation': round(pp, 4),
            'before_median_min': round(st.median([x for w in wks[:k] for x in wl[w]]), 1), 'after_median_min': round(st.median([x for w in wks[k:] for x in wl[w]]), 1)}
    out['changepoints'] = cps
    out['weekly_volume_cv'] = round(st.pstdev(wc) / st.mean(wc), 3) if st.mean(wc) else None
    if a.sample_out:   # 依月份分層抽樣，給「模型編碼」用（務必先經 anonymize.py）
        rng = random.Random(0); by_m = defaultdict(list)
        for i, m in enumerate(T):
            if len(m['text'].strip()) >= 2: by_m[f"{m['t']:%Y-%m}"].append(i)
        tot = max(1, sum(len(v) for v in by_m.values())); picked = []
        for k_, v in sorted(by_m.items()): picked += rng.sample(v, min(len(v), max(1, round(a.sample_n * len(v) / tot))))
        picked.sort()
        json.dump([{'id': j, 'ts': str(T[i]['t']), 'who': T[i]['who'], 'text': T[i]['text'][:200]} for j, i in enumerate(picked)],
                  open(a.sample_out, 'w'), ensure_ascii=False, indent=1)
    dc = Counter(m['t'].date() for m in M); top2 = sum(c for _, c in dc.most_common(2)) / len(M)
    warns = []
    if span < 14: warns.append(f'資料只有 {span} 天：穩定、趨勢、變點都沒有意義')
    if top2 > 0.6: warns.append(f'最忙的 2 天占全部訊息 {100*top2:.0f}%：疑似由活動／事件帶出的爆量，日常水位另看最近幾天')
    if out_excl: warns.append(f'已排除發言者（疑似機器人／系統）：{out_excl}，請確認沒有排錯人')
    if not out['reply_latency_reliable']: warns.append('回覆速度不可採用（同分鐘內來回或逐行傳送）')
    out['top2_days_share'] = round(top2, 3); out['warnings'] = warns
    print(json.dumps(out, ensure_ascii=False, indent=1))
main()
