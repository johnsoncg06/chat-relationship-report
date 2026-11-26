"""輕量工具（只用標準函式庫）：取代 pandas / numpy / scipy 在本專案用到的少數功能。
數值行為對齊原本的實作：percentile = numpy 線性內插；spearman p = t 分布；Mann-Whitney = scipy 預設（小樣本精確、否則常態近似含連續性與結同修正）。"""
import csv, math, datetime as dt
from collections import defaultdict


def load_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            r['ts'] = dt.datetime.fromisoformat(r['ts'])
            r['n_chars'] = int(r['n_chars'] or 0); r['session_id'] = int(r['session_id'])
            r['reply_latency_min'] = float(r['reply_latency_min']) if r['reply_latency_min'] not in ('', None) else None
            for k, v in list(r.items()):
                if k not in ('ts', 'who', 'kind', 'n_chars', 'session_id', 'reply_latency_min'): r[k] = int(float(v or 0))
            rows.append(r)
    return rows


def percentile(v, q):
    """numpy.percentile 的線性內插（q 為 0–100）。"""
    s = sorted(v); n = len(s)
    if n == 0: return float('nan')
    pos = (n - 1) * q / 100.0; lo = int(math.floor(pos)); hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def median(v): return percentile(v, 50)
def mean(v): return sum(v) / len(v)
def std(v, ddof=0):
    m = mean(v); return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - ddof))


def polyfit1(x, y):
    """一次最小平方：回傳 (斜率, 截距)。"""
    mx, my = mean(x), mean(y); sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx if sxx else 0.0
    return b, my - b * mx


def week_end(d):
    """pandas resample('W')（W-SUN）：每週以週日為標籤。"""
    return d + dt.timedelta(days=(6 - d.weekday()))


def weekly_counts(rows):
    """回傳 (週標籤清單, 次數清單)，含中間沒有訊息的空週。"""
    c = defaultdict(int)
    for r in rows: c[week_end(r['ts'].date())] += 1
    first, last = min(c), max(c); out_d, out_n = [], []; d = first
    while d <= last: out_d.append(d); out_n.append(c.get(d, 0)); d += dt.timedelta(days=7)
    return out_d, out_n


# ---- 統計分布 ----
def _betacf(a, b, x):
    tiny = 1e-300; qab, qap, qam = a + b, a + 1, a - 1; c = 1.0; d = 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 300):
        m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2)); d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c; c = c if abs(c) > tiny else tiny; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2)); d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c; c = c if abs(c) > tiny else tiny; de = d * c; h *= de
        if abs(de - 1) < 3e-16: break
    return h


def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b


def t_sf2(t, df):
    """雙尾 p：P(|T| >= |t|)。"""
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def norm_sf(z): return 0.5 * math.erfc(z / math.sqrt(2))


def rank_avg(v):
    idx = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]: j += 1
        for k in range(i, j + 1): r[idx[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = rank_avg(x), rank_avg(y); mx, my = mean(rx), mean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); sxx = sum((a - mx) ** 2 for a in rx); syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0: return float('nan'), float('nan')
    rho = sxy / math.sqrt(sxx * syy); n = len(x)
    if abs(rho) >= 1: return rho, 0.0
    return rho, t_sf2(rho * math.sqrt((n - 2) / (1 - rho * rho)), n - 2)


def _mw_exact_p(u, n1, n2):
    # 無結時 U 的精確分布（動態規劃計數）
    f = [[0] * (n1 * n2 + 1) for _ in range(1)]
    from functools import lru_cache
    @lru_cache(None)
    def cnt(m, n, k):
        if k < 0 or k > m * n: return 0
        if m == 0 or n == 0: return 1 if k == 0 else 0
        return cnt(m - 1, n, k - n) + cnt(m, n - 1, k)
    tot = math.comb(n1 + n2, n1); umin = min(u, n1 * n2 - u)
    p = 2 * sum(cnt(n1, n2, k) for k in range(int(umin) + 1)) / tot
    return min(1.0, p)


def mannwhitney_p(a, b):
    n1, n2 = len(a), len(b); allv = list(a) + list(b); r = rank_avg(allv)
    u1 = sum(r[:n1]) - n1 * (n1 + 1) / 2.0; u2 = n1 * n2 - u1
    ties = defaultdict(int)
    for v in allv: ties[v] += 1
    has_ties = any(c > 1 for c in ties.values())
    if n1 <= 8 and n2 <= 8 and not has_ties: return _mw_exact_p(u1, n1, n2)
    n = n1 + n2; tie_term = sum(c ** 3 - c for c in ties.values())
    s = math.sqrt(n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1))))
    if s == 0: return 1.0
    z = (max(u1, u2) - n1 * n2 / 2.0 - 0.5) / s
    return min(1.0, 2 * norm_sf(z))
