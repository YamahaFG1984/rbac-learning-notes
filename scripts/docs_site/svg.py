"""手绘 SVG 的极简 DSL。

只负责三件事：对齐（Box 提供锚点）、估算文字宽度、画箭头。
颜色一律交给页面 CSS 的 class（.bx / .ln / .t 及 acc / bad / good / warn / mut 修饰），
这样同一张图在浅色和深色主题下都能读。箭头头部用 polygon 直接算出来，
不用 <marker>，避免一页多图时 id 冲突。
"""

import math
from html import escape


def text_width(s, fs=13, mono=False):
    w = 0.0
    for ch in s:
        if ord(ch) >= 0x2E80:
            w += fs
        else:
            w += fs * (0.62 if mono else 0.56)
    return w


class Box:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    l = property(lambda s: s.x)
    r = property(lambda s: s.x + s.w)
    t = property(lambda s: s.y)
    b = property(lambda s: s.y + s.h)
    cx = property(lambda s: s.x + s.w / 2)
    cy = property(lambda s: s.y + s.h / 2)

    def left(self, dy=0):
        return (self.l, self.cy + dy)

    def right(self, dy=0):
        return (self.r, self.cy + dy)

    def top(self, dx=0):
        return (self.cx + dx, self.t)

    def bottom(self, dx=0):
        return (self.cx + dx, self.b)


def _n(v):
    v = round(v, 1)
    return str(int(v)) if v == int(v) else str(v)


class Fig:
    def __init__(self, w, h, label, min_width=None):
        self.w, self.h, self.label = w, h, label
        self.min_width = min_width if min_width is not None else int(w * 0.72)
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    # ---------- 基本元素 ----------

    def text(self, x, y, s, fs=13, anchor="middle", cls="", mono=False, bold=False,
             halo=False, rotate=None):
        c = ["t"]
        if mono:
            c.append("mono")
        if bold:
            c.append("b")
        if halo:
            c.append("halo")
        if cls:
            c.append(cls)
        tr = f' transform="rotate({rotate} {_n(x)} {_n(y)})"' if rotate else ""
        self.add(
            f'<text x="{_n(x)}" y="{_n(y)}" font-size="{fs}" text-anchor="{anchor}" '
            f'class="{" ".join(c)}"{tr}>{escape(s)}</text>'
        )

    def lines(self, cx, cy, rows, fs=13, anchor="middle", lh=None):
        """在 (cx, cy) 垂直居中排若干行。rows 元素为 str 或 (str, dict)。"""
        rows = [r if isinstance(r, tuple) else (r, {}) for r in rows]
        sizes = [o.get("fs", fs) for _, o in rows]
        lh = lh or 1.42
        heights = [s * lh for s in sizes]
        y = cy - sum(heights) / 2
        for (s, o), size, hgt in zip(rows, sizes, heights):
            opts = dict(o)
            opts.pop("fs", None)
            self.text(cx, y + hgt / 2 + size * 0.36, s, fs=size, anchor=anchor, **opts)
            y += hgt

    def rect(self, x, y, w, h, cls="bx", rx=6, dashed=False):
        extra = ' stroke-dasharray="5 4"' if dashed else ""
        self.add(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" '
                 f'rx="{rx}" class="{cls}"{extra}/>')

    def box(self, x, y, w, h, rows=(), kind="", fs=13, rx=6, dashed=False, anchor="middle",
            pad=10):
        cls = "bx" + (" " + kind if kind else "")
        self.rect(x, y, w, h, cls=cls, rx=rx, dashed=dashed)
        if isinstance(rows, str):
            rows = [rows]
        if rows:
            tx = x + w / 2 if anchor == "middle" else x + pad
            self.lines(tx, y + h / 2, rows, fs=fs, anchor=anchor)
        return Box(x, y, w, h)

    def zone(self, x, y, w, h, title=None, kind="", title_side="left"):
        self.rect(x, y, w, h, cls="zone" + (" " + kind if kind else ""), rx=10)
        if title:
            if title_side == "left":
                self.text(x + 12, y + 18, title, fs=12, anchor="start", cls="mut", bold=True)
            else:
                self.text(x + w - 12, y + 18, title, fs=12, anchor="end", cls="mut", bold=True)
        return Box(x, y, w, h)

    def ellipse(self, cx, cy, rx, ry, kind="", dashed=False):
        extra = ' stroke-dasharray="5 4"' if dashed else ""
        self.add(f'<ellipse cx="{_n(cx)}" cy="{_n(cy)}" rx="{_n(rx)}" ry="{_n(ry)}" '
                 f'class="bx {kind}"{extra}/>')

    def circle(self, cx, cy, r, kind=""):
        self.add(f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" class="dot {kind}"/>')

    def path(self, d, cls="ln", dashed=False, width=None):
        extra = ' stroke-dasharray="5 4"' if dashed else ""
        if width:
            extra += f' stroke-width="{width}"'
        self.add(f'<path d="{d}" class="{cls}"{extra}/>')

    # ---------- 箭头 ----------

    def _head(self, p, q, kind, size=7.5):
        (x1, y1), (x2, y2) = p, q
        ang = math.atan2(y2 - y1, x2 - x1)
        a1, a2 = ang + math.radians(152), ang - math.radians(152)
        pts = [(x2, y2),
               (x2 + size * math.cos(a1), y2 + size * math.sin(a1)),
               (x2 + size * math.cos(a2), y2 + size * math.sin(a2))]
        s = " ".join(f"{_n(a)},{_n(b)}" for a, b in pts)
        self.add(f'<polygon points="{s}" class="hd {kind}"/>')

    def arrow(self, pts, kind="", dashed=False, head=True, tail=False, label=None, seg=None,
              lpos=None, lanchor=None, fs=12, lcls=None, width=None, loff=7):
        pts = [tuple(p) for p in pts]
        # 线段在箭头处缩短一点，避免线头从三角形里戳出来
        draw = list(pts)
        if head:
            draw[-1] = _shorten(draw[-2], draw[-1], 5)
        if tail:
            draw[0] = _shorten(draw[1], draw[0], 5)
        d = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in draw)
        self.path(d, cls="ln" + (" " + kind if kind else ""), dashed=dashed, width=width)
        if head:
            self._head(pts[-2], pts[-1], kind, size=7.5 if not width else 6 + width)
        if tail:
            self._head(pts[1], pts[0], kind)
        if label:
            self._label(pts, label, seg, lpos, lanchor, fs, lcls if lcls is not None else kind,
                        loff)

    def _label(self, pts, label, seg, lpos, lanchor, fs, lcls, loff):
        if lpos:
            x, y = lpos
            self.text(x, y, label, fs=fs, anchor=lanchor or "middle", cls=lcls, halo=True)
            return
        if seg is None:
            lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            seg = lens.index(max(lens))
        (x1, y1), (x2, y2) = pts[seg], pts[seg + 1]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if abs(y2 - y1) <= abs(x2 - x1):      # 水平段：标在上方
            self.text(mx, my - loff, label, fs=fs, anchor=lanchor or "middle", cls=lcls,
                      halo=True)
        else:                                  # 垂直段：标在右侧
            self.text(mx + loff, my + fs * 0.36, label, fs=fs, anchor=lanchor or "start",
                      cls=lcls, halo=True)

    def curve(self, p0, c1, c2, p1, kind="", dashed=False, head=True, label=None, lpos=None,
              fs=12, lanchor="middle"):
        d = (f"M{_n(p0[0])} {_n(p0[1])} C{_n(c1[0])} {_n(c1[1])} "
             f"{_n(c2[0])} {_n(c2[1])} {_n(p1[0])} {_n(p1[1])}")
        self.path(d, cls="ln" + (" " + kind if kind else ""), dashed=dashed)
        if head:
            self._head(c2, p1, kind)
        if label and lpos:
            self.text(lpos[0], lpos[1], label, fs=fs, anchor=lanchor, cls=kind, halo=True)

    def elbow_down(self, a, b, kind="", mid=None, **kw):
        """父节点底部 → 子节点顶部的直角连线（树形图用）。"""
        (x1, y1), (x2, y2) = a.bottom(), b.top()
        my = mid if mid is not None else (y1 + y2) / 2
        self.arrow([(x1, y1), (x1, my), (x2, my), (x2, y2)], kind=kind, head=False, **kw)

    def link(self, href, inner):
        """把之前 add 的最后 inner 个元素包进 <a>。"""
        grp = self.parts[-inner:]
        del self.parts[-inner:]
        self.add(f'<a href="{escape(href, quote=True)}">' + "".join(grp) + "</a>")

    # ---------- 输出 ----------

    def svg(self):
        body = "\n".join(self.parts)
        return (
            f'<svg viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.label)}" '
            f'style="max-width:{self.w}px;min-width:{self.min_width}px" '
            f'xmlns="http://www.w3.org/2000/svg">\n{body}\n</svg>'
        )


def _shorten(p, q, by):
    (x1, y1), (x2, y2) = p, q
    d = math.dist(p, q)
    if d <= by:
        return q
    t = (d - by) / d
    return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
