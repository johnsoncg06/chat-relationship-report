"""極簡 SVG 繪圖（只用標準函式庫）：取代 matplotlib。輸出的 SVG 由瀏覽器渲染，中文字型用系統字型，不需內建字型。"""
import math
from xml.sax.saxutils import escape

FONT = "'PingFang TC','Microsoft JhengHei','Noto Sans TC','Noto Sans CJK TC','Heiti TC','Segoe UI',sans-serif"
COL = ['#2a6fdb', '#e8590c', '#2f9e44', '#9c36b5', '#868e96', '#c2255c']
INK, MUTE, GRID = '#343a40', '#868e96', '#e9ecef'


def f(v): return f'{v:.1f}'.rstrip('0').rstrip('.') if abs(v) < 1e6 else str(int(v))


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h; self.e = []

    def add(self, s): self.e.append(s)

    def rect(self, x, y, w, h, fill='none', stroke=None, op=None, sw=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''; o = f' fill-opacity="{op}"' if op is not None else ''
        self.add(f'<rect x="{f(x)}" y="{f(y)}" width="{f(max(w, 0))}" height="{f(max(h, 0))}" fill="{fill}"{o}{st}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1, dash=None, op=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''; o = f' stroke-opacity="{op}"' if op is not None else ''
        self.add(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')

    def poly(self, pts, stroke=INK, sw=1.6, fill='none', op=None, dash=None, close=False):
        if not pts: return
        p = ' '.join(f'{f(x)},{f(y)}' for x, y in pts); d = f' stroke-dasharray="{dash}"' if dash else ''
        o = f' fill-opacity="{op}"' if op is not None else ''; tag = 'polygon' if close else 'polyline'
        self.add(f'<{tag} points="{p}" fill="{fill}"{o} stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"{d}/>')

    def circle(self, x, y, r, fill=INK, stroke=None, sw=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
        self.add(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="{fill}"{st}/>')

    def text(self, x, y, s, size=12, anchor='start', fill=INK, weight='normal', rot=None, base=None):
        r = f' transform="rotate({rot} {f(x)} {f(y)})"' if rot else ''; b = f' dominant-baseline="{base}"' if base else ''
        self.add(f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"{b}{r}>{escape(str(s))}</text>')

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" font-family="{FONT}">'
                     f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>' + ''.join(self.e) + '</svg>')


def nice_ticks(lo, hi, n=5):
    if hi <= lo: hi = lo + 1
    raw = (hi - lo) / max(n, 1); mag = 10 ** math.floor(math.log10(raw)); step = mag
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if raw <= step: break
    t = math.ceil(lo / step) * step; out = []
    while t <= hi + 1e-9: out.append(round(t, 10)); t += step
    return out


def fmt(v):
    return str(int(v)) if abs(v - round(v)) < 1e-9 else f'{v:g}'


class Axes:
    """在 (x,y,w,h) 區域內畫座標軸。xs/ys 可為 'lin' 或 'log'。"""
    def __init__(self, svg, x, y, w, h, xlim, ylim, xs='lin', ys='lin', title=None, xlabel=None, ylabel=None, tsize=13):
        self.s, self.x, self.y, self.w, self.h = svg, x, y, w, h; self.xlim, self.ylim, self.xs, self.ys = xlim, ylim, xs, ys
        if title: svg.text(x + w / 2, y - 8, title, tsize, 'middle', INK, 'bold')
        if xlabel: svg.text(x + w / 2, y + h + 38, xlabel, 11, 'middle', MUTE)
        if ylabel: svg.text(x - 38, y + h / 2, ylabel, 11, 'middle', MUTE, rot=-90)

    def _t(self, v, lim, sc):
        lo, hi = lim
        if sc == 'log': v, lo, hi = math.log10(max(v, 1e-12)), math.log10(lo), math.log10(hi)
        return (v - lo) / (hi - lo) if hi != lo else 0.5

    def px(self, v): return self.x + self._t(v, self.xlim, self.xs) * self.w
    def py(self, v): return self.y + self.h - self._t(v, self.ylim, self.ys) * self.h

    def frame(self, xticks=None, yticks=None, grid=True, xrot=None, ylab=None):
        s = self.s
        xt = xticks if xticks is not None else self._auto(self.xlim, self.xs, 6)
        yt = yticks if yticks is not None else self._auto(self.ylim, self.ys, 5)
        for v, lab in yt:
            yy = self.py(v) if not isinstance(v, str) else None
            if yy is None: continue
            if grid: s.line(self.x, yy, self.x + self.w, yy, GRID, 1)
            s.text(self.x - 6, yy + 4, lab, 10, 'end', MUTE)
        for v, lab in xt:
            xx = self.px(v)
            if grid: s.line(xx, self.y, xx, self.y + self.h, GRID, 1)
            if xrot: s.text(xx, self.y + self.h + 14, lab, 10, 'end', MUTE, rot=xrot)
            else: s.text(xx, self.y + self.h + 15, lab, 10, 'middle', MUTE)
        s.line(self.x, self.y + self.h, self.x + self.w, self.y + self.h, '#adb5bd', 1); s.line(self.x, self.y, self.x, self.y + self.h, '#adb5bd', 1)

    def _auto(self, lim, sc, n):
        if sc == 'log':
            lo, hi = math.floor(math.log10(lim[0])), math.ceil(math.log10(lim[1]))
            t = [(m * 10 ** e, fmt(m * 10 ** e)) for e in range(lo - 1, hi + 1) for m in (1, 2, 5) if lim[0] * 0.999 <= m * 10 ** e <= lim[1] * 1.001]
            full = [x for x in t if x[0] in [10 ** e for e in range(lo - 1, hi + 1)]]
            return full if len(full) >= 3 else t
        return [(v, fmt(v)) for v in nice_ticks(lim[0], lim[1], n) if lim[0] - 1e-9 <= v <= lim[1] + 1e-9]

    def clipbox(self):
        return self


def legend(svg, x, y, items, size=11):
    """items: [(label, color)]，由 (x,y) 往右依序排。"""
    cx = x
    for lab, c in items:
        svg.rect(cx, y - 9, 12, 12, c); svg.text(cx + 17, y + 1, lab, size, 'start', INK); cx += 24 + len(str(lab)) * (size * 0.95) + 10
    return cx


def ramp(t, stops):
    t = min(1.0, max(0.0, t)); n = len(stops) - 1; i = min(int(t * n), n - 1); u = t * n - i
    a, b = stops[i], stops[i + 1]; return '#%02x%02x%02x' % tuple(int(a[k] + (b[k] - a[k]) * u) for k in range(3))


YLORRD = [(255, 255, 204), (254, 217, 118), (253, 141, 60), (227, 26, 28), (128, 0, 38)]


def kde(vals, grid):
    n = len(vals)
    if n < 2: return [0.0] * len(grid)
    m = sum(vals) / n; sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1)) or 1e-6; bw = sd * n ** (-0.2)
    if n > 1500: vals = vals[::max(1, n // 1500)]; n = len(vals)
    c = 1 / (n * bw * math.sqrt(2 * math.pi))
    return [c * sum(math.exp(-0.5 * ((g - v) / bw) ** 2) for v in vals) for g in grid]
