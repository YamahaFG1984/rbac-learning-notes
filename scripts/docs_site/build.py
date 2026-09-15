#!/usr/bin/env python3
"""把 docs/ 下的 Markdown 构建成可部署到 GitHub Pages 的静态站点。

    pip install -r scripts/docs_site/requirements.txt
    python scripts/docs_site/build.py              # 输出到 _site/
    python scripts/docs_site/build.py --out DIR

docs/ 下的 Markdown 原文一个字都不改：示意图按 PLACEMENTS 里的锚点在构建时插入，
被图替换掉的字符画保留在图下方的「文字版」折叠块里。锚点找不到时构建直接失败，
免得文档改了之后图悄悄消失。
"""

import argparse
import html
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figures import FIGS, MILESTONES, TAGS  # noqa: E402

REPO = HERE.parent.parent
DOCS = REPO / "docs"
GITHUB = "https://github.com/YamahaFG1984/rbac-learning-notes"
SITE_NAME = "RBAC 学习笔记"

MAIN_DOCS = [
    # (源文件, 编号, 导航名, 简介, 阅读提示)
    ("00-RBAC理论基础.md", "00", "RBAC 理论基础",
     "访问控制模型的演进、NIST RBAC 四个层级，以及数据权限为什么在标准里找不到位置。", "前置阅读 · 约 40 分钟"),
    ("01-PRD.md", "01", "PRD 需求文档",
     "要做什么、给谁用、怎么验收。FR / NFR / AC 编号都在这里定义。", "约 30 分钟"),
    ("02-设计文档.md", "02", "设计文档",
     "16 条 ADR（问题 → 候选 → 决定 → 理由 → 代价）、数据模型、核心算法、安全设计。", "全文核心 · 约 90 分钟"),
    ("03-实施计划.md", "03", "实施计划",
     "23 个 tag 的总纲与索引、贯穿全项目的原则、学习自检清单。", "约 20 分钟"),
    ("04-横向对比.md", "04", "横向对比",
     "与 Django 原生 / django-guardian / Casbin / 若依逐项对照，附选型决策树。", "建议完成 v0.14.0 后再读"),
]

# 示意图的插入位置。op：
#   replace      —— 替换内容含 marker 的代码块（原文保留在「文字版」折叠块里）
#   after_block  —— 插在内容含 marker 的代码块之后
#   after_heading—— 插在与 marker 完全相同的标题行之后
#   before_line  —— 插在以 marker 开头的行之前
#   after_line   —— 插在含 marker 的行所在段落之后
#   after_h1     —— 插在一级标题之后
PLACEMENTS = {
    "00-RBAC理论基础.md": [
        ("replace", "no read up", "blp"),
        ("replace", "（N × M 条关系）", "acl_vs_rbac"),
        ("replace", "USERS ────UA", "rbac0"),
        ("replace", "│  继承", "role_chain"),
        ("after_heading", "### 3.5 四层对比", "nist_levels"),
        ("after_heading", "### 6.2 于是出现了两条路", "two_routes"),
    ],
    "01-PRD.md": [
        ("after_heading", "## 8. 里程碑", "roadmap"),
    ],
    "02-设计文档.md": [
        ("replace", "│  表现层", "architecture"),
        ("replace", "audit   ──┼──> rbac", "deps"),
        ("after_block", "Department.objects.filter(path__startswith=dept.path, is_active=True)", "dept_path"),
        ("replace", "📁 catalog（目录）", "perm_tree"),
        ("before_line", "**单继承 vs 多继承**", "inherit_semantics"),
        ("after_line", "编号顺序不是随意的", "scope_coverage"),
        ("after_block", "q = Q(creator=user) | Q(department_id__in=市场部子树ID集)", "union"),
        ("after_line", "> 你应该能通过 `grep` 找出所有绕过数据权限的查询。方案 b", "implicit"),
        ("after_line", "要逐个删 key，就得先反查出这批用户 ID", "invalidation"),
        ("after_line", "L1 是零成本的纯收益", "cache_levels"),
        ("after_line", "注册为 Django 的 system check", "wrapper_chain"),
        ("after_line", "这一点会在代码注释、文档和测试用例里出现多次", "three_layers"),
        ("replace", "erDiagram", "er"),
        ("after_block", "def expand_roles(roles):", "expand_roles"),
        ("before_line", "**这个函数里有四处「默认拒绝」", "scope_flow"),
        ("after_block", "def get_user_menu_tree(user):", "menu_prune"),
        ("replace", "浏览器 GET /tickets/", "request_flow"),
        ("replace", "管理员保存角色权限", "bump_flow"),
        ("replace", "他部门单", "matrix"),
    ],
    "03-实施计划.md": [
        ("replace", "1. 读该 tag 的指南", "learning_loop"),
        ("after_heading", "## 4. Tag 索引", "roadmap"),
    ],
    "04-横向对比.md": [
        ("after_heading", "### 4.2 它和数据权限是两种东西", "two_routes"),
        ("after_block", "# 路 A：全表扫描后逐行判断", "pushdown"),
        ("before_line", "| | 字符串拼接 | Q 对象 |", "ruoyi_vs_q"),
        ("replace", "需要「列出我能看的所有数据」这类集合查询吗？", "decision_tree"),
    ],
    # tag 指南里的图只放在「答案已经揭晓」的位置（五、陷阱 / 八、对比），不剧透思考题
    "tags/03-v0.3.0-部门树.md": [
        ("after_block", '"/11/".startswith("/1/")', "dept_path"),
    ],
    "tags/09-v0.9.0-视图鉴权与启动自检.md": [
        ("before_line", "### 3. 检查 Mixin 时要看类属性", "wrapper_chain"),
    ],
    "tags/10-v0.10.0-模板层权限渲染.md": [
        ("before_line", "**只有第一层是安全的", "three_layers"),
    ],
    "tags/11-v0.11.0-动态菜单树.md": [
        ("replace", "❌ 自顶向下", "menu_prune"),
    ],
    "tags/12-v0.12.0-角色继承RBAC1.md": [
        ("before_line", "**纵深防御**", "expand_roles"),
    ],
    "tags/14-v0.14.0-数据权限.md": [
        ("after_block", "# ✅ 真并集", "union"),
        ("before_line", "> **显式优于隐式**", "implicit"),
        ("after_heading", "## 八、写完之后，和我的实现对比什么", "scope_flow"),
    ],
    "tags/15-v0.15.0-自定义范围与单条校验.md": [
        ("before_line", "这是 OWASP 明确建议的做法", "404"),
    ],
    "tags/16-v0.16.0-权限缓存.md": [
        ("after_block", "# ✅ 绝不会漏", "invalidation"),
        ("before_line", "代价是每次多一次 `cache.get(版本号)`", "cache_levels"),
    ],
    "tags/19-v0.19.0-测试套件.md": [
        ("replace", "他部门单", "matrix"),
    ],
    "tags/22-v1.2.0-API权限复用.md": [
        ("after_line", "**现在收益兑现了**", "architecture"),
    ],
}

FIG_RE = re.compile(r"<!--FIG:(\w+):(\d+)-->")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


# ------------------------------------------------------------------ 插图

def find_fences(lines):
    blocks, i = [], 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            fence = m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith(fence[0] * len(fence)):
                j += 1
            blocks.append((i, min(j, len(lines) - 1)))
            i = j + 1
        else:
            i += 1
    return blocks


def apply_placements(text, ops, src):
    lines = text.split("\n")
    blocks = find_fences(lines)
    in_fence = set()
    for s, e in blocks:
        in_fence.update(range(s, e + 1))
    inserts, replaced, sources = {}, {}, []

    def placeholder(name, original=None):
        sources.append(original)
        return f"<!--FIG:{name}:{len(sources) - 1}-->"

    def plain_lines():
        return [i for i in range(len(lines)) if i not in in_fence]

    for op, marker, name in ops:
        if name not in FIGS:
            raise SystemExit(f"{src}: 未定义的图 {name}")
        if op in ("replace", "after_block"):
            hits = [(s, e) for s, e in blocks if marker in "\n".join(lines[s:e + 1])]
            if not hits:
                raise SystemExit(f"{src}: 找不到含 {marker!r} 的代码块")
            s, e = hits[0]
            if op == "replace":
                original = "\n".join(lines[s + 1:e])
                lang = FENCE_RE.match(lines[s]).group(0).strip().lstrip("`~")
                replaced[s] = (e, placeholder(name, (lang or lines[s].strip().lstrip("`~"), original)))
            else:
                inserts.setdefault(e + 1, []).append(placeholder(name))
            continue
        if op == "after_h1":
            idx = next(i for i in plain_lines() if lines[i].startswith("# "))
            inserts.setdefault(idx + 1, []).append(placeholder(name))
            continue
        cands = plain_lines()
        if op == "after_heading":
            hits = [i for i in cands if lines[i].strip() == marker]
        elif op == "before_line":
            hits = [i for i in cands if lines[i].strip().startswith(marker)]
        else:
            hits = [i for i in cands if marker in lines[i]]
        if not hits:
            raise SystemExit(f"{src}: 找不到锚点 {op} {marker!r}")
        i = hits[0]
        if op == "after_heading":
            at = i + 1
        elif op == "before_line":
            at = i
        else:
            at = i
            while at < len(lines) and lines[at].strip():
                at += 1
        inserts.setdefault(at, []).append(placeholder(name))

    out, i = [], 0
    while i <= len(lines):
        for ph in inserts.get(i, []):
            out += ["", ph, ""]
        if i == len(lines):
            break
        if i in replaced:
            end, ph = replaced[i]
            out += ["", ph, ""]
            i = end + 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), sources


def render_figure(name, number, ctx, source):
    body, caption = FIGS[name](ctx)
    fid = f"fig-{name}"
    if caption is None:
        return f'<figure class="fig strip"><div class="fig-scroll">{body}</div></figure>'
    cap = f"<b>图 {number}</b>{html.escape(caption)}"
    src_html = ""
    if source:
        lang, text = source
        label = "查看 Mermaid 源码" if lang == "mermaid" else "查看原文字版"
        src_html = (f'<details class="fig-src"><summary>{label}</summary>'
                    f"<pre><code>{html.escape(text)}</code></pre></details>")
    return (f'<figure class="fig" id="{fid}-{number}"><div class="fig-scroll">{body}</div>'
            f"<figcaption>{cap}</figcaption>{src_html}</figure>")


# ------------------------------------------------------------------ Markdown

def github_slug(title):
    """与 GitHub 的标题锚点规则一致，文档里手写的 #锚点 链接才能继续用。"""
    s = re.sub(r"[^\w\- ]", "", title.strip().lower())
    return s.replace(" ", "-")


def _highlight(code, lang, _attrs):
    lang = (lang or "").strip()
    if not lang or lang == "mermaid":
        return ""
    alias = {"django": "html+django"}.get(lang, lang)
    try:
        lexer = get_lexer_by_name(alias)
    except ClassNotFound:
        return ""
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


class Renderer:
    def __init__(self):
        md = MarkdownIt("commonmark", {"html": True, "highlight": _highlight})
        md.enable(["table", "strikethrough"])
        md.use(anchors_plugin, min_level=1, max_level=4, slug_func=github_slug, permalink=True,
               permalinkSymbol="#")
        md.use(tasklists_plugin)
        md.add_render_rule("table_open", lambda *a: '<div class="table-wrap"><table>\n')
        md.add_render_rule("table_close", lambda *a: "</table></div>\n")
        # add_render_rule 会把函数绑定到 renderer 上，所以这里用闭包而不是绑定方法
        md.add_render_rule("link_open", lambda renderer, *a: self._link_open(renderer, *a))
        self.md = md
        self.src = None
        self.links = []

    def _link_open(self, renderer, tokens, idx, options, env):
        tok = tokens[idx]
        href = tok.attrGet("href") or ""
        new, target = rewrite_link(href, self.src)
        tok.attrSet("href", new)
        if new.startswith("http"):
            tok.attrSet("target", "_blank")
            tok.attrSet("rel", "noopener")
        if target:
            self.links.append((self.src, *target))
        return renderer.renderToken(tokens, idx, options, env)

    def render(self, text, src):
        self.src = src
        tokens = self.md.parse(text)
        toc, ids, title = [], set(), None
        for i, t in enumerate(tokens):
            if t.type != "heading_open":
                continue
            hid = t.attrGet("id")
            ids.add(hid)
            words = []
            for c in tokens[i + 1].children or []:
                if c.type == "link_open" and "header-anchor" in (c.attrGet("class") or ""):
                    break
                if c.type in ("text", "code_inline"):
                    words.append(c.content)
            label = "".join(words).strip()
            if t.tag == "h1" and title is None:
                title = label
            elif t.tag in ("h2", "h3"):
                toc.append((t.tag, hid, label))
        body = self.md.renderer.render(tokens, self.md.options, {})
        return body, toc, ids, title

    def inline(self, text, src):
        self.src = src
        return self.md.renderInline(text)


def rewrite_link(href, src):
    """src 为相对 docs/ 的源文件路径。返回 (新 href, (目标页, 锚点) 或 None)。"""
    if re.match(r"^[a-z][a-z0-9+.-]*:", href) or href.startswith("#"):
        if href.startswith("#"):
            return href, (md_to_html(src), unquote(href[1:]))
        return href, None
    path, _, frag = href.partition("#")
    path = unquote(path)
    base = posixpath.dirname(src)
    target = posixpath.normpath(posixpath.join(base, path)) if path else src
    frag_s = "#" + unquote(frag) if frag else ""
    if target.startswith(".."):  # 指向 docs/ 之外：去 GitHub 看源码
        repo_path = posixpath.normpath(posixpath.join("docs", base, path))
        kind = "tree" if path.endswith("/") or (REPO / repo_path).is_dir() else "blob"
        return f"{GITHUB}/{kind}/main/{quote(repo_path)}{frag_s}", None
    if path.endswith("/") or (DOCS / target).is_dir():
        out = target.rstrip("/") + "/index.html"
    elif target.endswith(".md"):
        out = md_to_html(target)
    else:
        return f"{GITHUB}/blob/main/{quote('docs/' + target)}{frag_s}", None
    rel = posixpath.relpath(out, base or ".")
    return quote(rel) + frag_s, (out, unquote(frag) if frag else None)


def md_to_html(p):
    return p[:-3] + ".html" if p.endswith(".md") else p


# ------------------------------------------------------------------ 页面骨架

def tag_pages():
    return [t for t in TAGS if t[5]]


def reading_order():
    order = [(d[0], f"{d[1]} {d[2]}") for d in MAIN_DOCS[:4]]
    order += [(f"tags/{t[5]}.md", f"{t[0]} {t[2]}") for t in tag_pages()]
    order.append((MAIN_DOCS[4][0], f"04 {MAIN_DOCS[4][2]}"))
    return [(md_to_html(p), label) for p, label in order]


def href(root, key):
    return root + quote(key)


def sidebar(cur, root):
    def a(key, label, ver="", mark=""):
        cls = ' class="active" aria-current="page"' if key == cur else ""
        v = f'<span class="ver">{ver}</span>' if ver else ""
        m = f'<span class="mark">{mark}</span>' if mark else ""
        return f'<a href="{href(root, key)}"{cls}>{v}<span>{html.escape(label)}</span>{m}</a>'

    out = ['<nav class="sidebar" aria-label="文档导航">', "<h4>主文档</h4>",
           a("index.html", "首页 · 阅读路线")]
    for fn, num, name, *_ in MAIN_DOCS:
        out.append(a(md_to_html(fn), name, ver=num))
    out.append("<h4>Tag 指南</h4>")
    out.append(a("tags/index.html", "全部 22 个 tag 一览"))
    last = None
    for ver, short, full, ms, mark, fname in tag_pages():
        if ms != last:
            out.append(f'<div class="ms">{ms} · {MILESTONES[ms]}</div>')
            last = ms
        sym = {"warn": "⚠", "bad": "🔴", "acc": "🎯"}.get(mark, "")
        out.append(a(f"tags/{fname}.html", full, ver=ver, mark=sym))
    out.append("</nav>")
    return "\n".join(out)


def toc_html(toc):
    if len(toc) < 3:
        return '<aside class="toc"></aside>'
    items = "".join(
        f'<a class="{"l3" if tag == "h3" else "l2"}" href="#{html.escape(hid, quote=True)}">'
        f"{html.escape(label)}</a>"
        for tag, hid, label in toc
    )
    return f'<aside class="toc" aria-label="本页目录"><h4>本页目录</h4>{items}</aside>'


def pager(cur, root):
    order = reading_order()
    keys = [k for k, _ in order]
    if cur not in keys:
        return ""
    i = keys.index(cur)
    parts = []
    if i > 0:
        k, label = order[i - 1]
        parts.append(f'<a class="prev" href="{href(root, k)}"><small>← 上一篇</small>{html.escape(label)}</a>')
    if i < len(order) - 1:
        k, label = order[i + 1]
        parts.append(f'<a class="next" href="{href(root, k)}"><small>下一篇 →</small>{html.escape(label)}</a>')
    return f'<nav class="pager" aria-label="翻页">{"".join(parts)}</nav>'


def page(title, body, cur, root, toc=(), source=None):
    src_link = ""
    if source:
        src_link = (f'<p class="footer">本页由 <a href="{GITHUB}/blob/main/{quote("docs/" + source)}" '
                    f'target="_blank" rel="noopener">docs/{html.escape(source)}</a> 生成。</p>')
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(title)} · {SITE_NAME}</title>
<link rel="stylesheet" href="{root}assets/site.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔐</text></svg>">
<script>try{{var t=localStorage.getItem("rbac-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
</head>
<body>
<header class="topbar">
  <button class="icon-btn menu-btn" id="menu-btn" aria-label="打开导航">☰</button>
  <a class="brand" href="{root}index.html">{SITE_NAME}<small>Django 5.2 · RBAC1 + 数据权限</small></a>
  <span class="spacer"></span>
  <a class="gh-link" href="{GITHUB}" target="_blank" rel="noopener">GitHub 仓库 ↗</a>
  <button class="icon-btn" id="theme-btn" type="button">◐ 跟随系统</button>
</header>
<div class="layout">
{sidebar(cur, root)}
<main><article class="article">
{body}
{pager(cur, root)}
{src_link}
</article></main>
{toc_html(toc)}
</div>
<script src="{root}assets/site.js"></script>
</body>
</html>
"""


# ------------------------------------------------------------------ 构建

def build_doc(r, src, fig_numbers=None):
    text = (DOCS / src).read_text(encoding="utf-8")
    ops = list(PLACEMENTS.get(src, []))
    tag = None
    if src.startswith("tags/"):
        fname = Path(src).stem
        tag = next(t[0] for t in TAGS if t[5] == fname)
        ops.insert(0, ("after_h1", "", "tag_strip"))
    text, sources = apply_placements(text, ops, src)
    body, toc, ids, title = r.render(text, src)
    root = "../" if src.startswith("tags/") else ""
    ctx = {"root": root, "tag": tag}
    counter = [0]

    def repl(m):
        name, k = m.group(1), int(m.group(2))
        if FIGS[name](ctx)[1] is not None:
            counter[0] += 1
        return render_figure(name, counter[0], ctx, sources[k])

    body = FIG_RE.sub(repl, body)
    ids.update(re.findall(r'<figure class="fig" id="([^"]+)"', body))
    return title, body, toc, ids, root, counter[0]


def tag_meta(src):
    meta = {}
    for line in (DOCS / src).read_text(encoding="utf-8").splitlines()[:14]:
        m = re.match(r"^\|\s*(需求|关键 ADR|预计耗时|变更规模)\s*\|\s*(.*?)\s*\|\s*$", line)
        if m:
            meta[m.group(1)] = m.group(2)
    return meta


def build_index(r):
    cards = []
    for fn, num, name, desc, hint in MAIN_DOCS[:4]:
        cards.append((md_to_html(fn), num, name, desc, hint))
    cards.append(("tags/index.html", "tags", "22 份 Tag 指南",
                  "每个 tag 一份可独立实现的规格书：思考题、接口契约、陷阱、渐进提示、自测清单、对比检查点。",
                  "约 55 ~ 75 小时"))
    fn, num, name, desc, hint = MAIN_DOCS[4]
    cards.append((md_to_html(fn), num, name, desc, hint))
    card_html = "".join(
        f'<a class="card" href="{quote(k)}"><span class="num">{i + 1:02d} · {html.escape(num)}</span>'
        f"<h3>{html.escape(n)}</h3><p>{html.escape(d)}</p><span class=\"time\">{html.escape(h)}</span></a>"
        for i, (k, num, n, d, h) in enumerate(cards)
    )
    road_svg, road_cap = FIGS["roadmap"]({"root": "", "tag": None})
    body = f"""
<section class="hero">
<h1>用 Django 5.2 从零实现一套企业级 RBAC 权限系统</h1>
<p class="lead">一个教学导向的工程项目：把「一套 RBAC 系统是怎么一步步长出来的」完整、可复现地记录下来——包括每一处设计取舍的<strong>理由</strong>和<strong>代价</strong>。
本站是仓库 <code>docs/</code> 目录的网页版，另外补了 20 多张示意图。</p>
</section>
<h2 id="reading">阅读路线</h2>
<p>按卡片顺序读。前四份文档约 3 小时；tag 指南建议「先自己实现，再 <code>git diff</code> 对比」；横向对比放在最后，等你亲手踩过坑再读。</p>
<div class="cards">{card_html}</div>
<h2 id="roadmap">23 个 tag 的路线图</h2>
<p>每一行都能点进对应的 tag 指南。</p>
<figure class="fig" id="fig-roadmap-home"><div class="fig-scroll">{road_svg}</div><figcaption>{html.escape(road_cap)}</figcaption></figure>
<h2 id="how">两种学习方式</h2>
<div class="table-wrap"><table>
<thead><tr><th>方式</th><th>做法</th><th>耗时</th></tr></thead>
<tbody>
<tr><td><strong>A. 自己实现，再对比</strong>（推荐）</td><td>读 tag 指南 → 做思考题 → 照「接口契约」自己写 → 跑自测清单 → <code>git diff</code> 对照参考实现</td><td>约 55 ~ 75 小时</td></tr>
<tr><td><strong>B. 只读代码和 diff</strong></td><td><code>git diff v0.5.0 v0.6.0 -- ':!static/css/tailwind.css'</code>，再读指南的「陷阱」「对比点」「延伸思考」三节</td><td>约 10 小时</td></tr>
</tbody></table></div>
<pre><code>git clone {GITHUB}.git
cd rbac-learning-notes
git tag -l            # 23 个 tag，每个都能 migrate + runserver</code></pre>
"""
    return page("首页", body, "index.html", "")


def build_tags_index(r):
    rows = []
    for i, (ver, short, full, ms, mark, fname) in enumerate(tag_pages(), 1):
        src = f"tags/{fname}.md"
        m = tag_meta(src)
        sym = {"warn": " ⚠", "bad": " 🔴", "acc": " 🎯"}.get(mark, "")
        rows.append(
            f"<tr><td>{i}</td><td><code>{ver}</code></td>"
            f'<td><a href="{quote(fname)}.html">{html.escape(full)}</a>{sym}</td>'
            f"<td>{r.inline(m.get('需求', ''), src)}</td>"
            f"<td>{r.inline(m.get('关键 ADR', ''), src)}</td>"
            f"<td>{html.escape(m.get('预计耗时', ''))}</td><td>{html.escape(m.get('变更规模', ''))}</td></tr>"
        )
    body = f"""
<h1 id="tag-指南一览">Tag 指南一览</h1>
<p>每份指南的结构都一样：一、思考题 → 二、交付物 → 三、接口契约（照抄）→ 四、实现步骤 → 五、陷阱 → 六、渐进提示（折叠）→ 七、自测清单 → 八、对比检查点 → 九、延伸思考。
总纲见 <a href="../03-{quote('实施计划')}.html">03 实施计划</a>。⚠ 为刻意留下的不安全中间态，🔴 为最容易写出漏洞的 tag，🎯 为架构检验点。</p>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>tag</th><th>内容</th><th>需求</th><th>关键 ADR</th><th>耗时</th><th>规模</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
"""
    return page("Tag 指南一览", body, "tags/index.html", "../")


def pygments_css():
    def defs(style, prefix):
        out = []
        for line in HtmlFormatter(style=style).get_style_defs(".article pre code").splitlines():
            if not line.startswith(".article pre code ."):
                continue
            out.append(prefix + line if prefix else line)
        return "\n".join(out)

    light = defs("default", "")
    dark_rules = defs("github-dark", "")
    dark_forced = "\n".join(':root[data-theme="dark"] ' + ln for ln in dark_rules.splitlines())
    dark_auto = "\n".join(':root:not([data-theme="light"]) ' + ln for ln in dark_rules.splitlines())
    return f"{light}\n@media (prefers-color-scheme: dark) {{\n{dark_auto}\n}}\n{dark_forced}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(REPO / "_site"))
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "tags").mkdir(parents=True)
    (out / "assets").mkdir()

    r = Renderer()
    all_ids, pages, figs = {}, 0, 0
    sources = [d[0] for d in MAIN_DOCS] + [f"tags/{t[5]}.md" for t in tag_pages()]
    for src in sources:
        title, body, toc, ids, root, n = build_doc(r, src)
        key = md_to_html(src)
        all_ids[key] = ids
        (out / key).write_text(page(title or src, body, key, root, toc, source=src), encoding="utf-8")
        pages += 1
        figs += n
    (out / "index.html").write_text(build_index(r), encoding="utf-8")
    (out / "tags" / "index.html").write_text(build_tags_index(r), encoding="utf-8")
    all_ids["index.html"] = set()
    all_ids["tags/index.html"] = set()

    css = (HERE / "assets" / "site.css").read_text(encoding="utf-8") + pygments_css()
    (out / "assets" / "site.css").write_text(css, encoding="utf-8")
    shutil.copy(HERE / "assets" / "site.js", out / "assets" / "site.js")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    broken = []
    for src, target, frag in r.links:
        if target not in all_ids:
            broken.append(f"  {src}: 目标页面不存在 {target}")
        elif frag and frag not in all_ids[target]:
            broken.append(f"  {src}: {target} 中没有锚点 #{frag}")
    print(f"已生成 {pages + 2} 个页面、{figs} 张编号图 → {out}")
    if broken:
        print("⚠ 以下链接在源文档里就指向了不存在的位置（未修改源文档）：")
        print("\n".join(sorted(set(broken))))


if __name__ == "__main__":
    main()
