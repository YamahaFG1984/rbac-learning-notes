"""文档站的全部示意图。

每个函数返回 (svg, caption)。图只画机制——数据怎么流、哪条边在两个方案之间不同、
请求经过哪些关口；能用一句话说清的东西不画。
"""

from svg import Box, Fig, text_width

# ------------------------------------------------------------------ 数据

TAGS = [
    # (version, 短名, 全名, 里程碑, 标记, 文件名)
    ("v0.0.1-docs", "文档", "文档定稿", "M0", "", None),
    ("v0.1.0", "骨架", "项目骨架", "M1", "", "01-v0.1.0-项目骨架"),
    ("v0.2.0", "用户模型", "自定义 User 模型", "M1", "", "02-v0.2.0-自定义用户模型"),
    ("v0.3.0", "部门树", "部门树", "M1", "", "03-v0.3.0-部门树"),
    ("v0.4.0", "权限点", "权限点与代码化声明", "M2", "", "04-v0.4.0-权限点与代码化声明"),
    ("v0.5.0", "角色", "角色与角色-权限绑定", "M2", "", "05-v0.5.0-角色与角色权限绑定"),
    ("v0.6.0", "权限解析", "用户角色与权限解析", "M2", "", "06-v0.6.0-用户角色与权限解析"),
    ("v0.7.0", "认证", "认证与会话", "M2", "", "07-v0.7.0-认证与会话"),
    ("v0.8.0", "布局", "后台布局", "M3", "warn", "08-v0.8.0-后台布局"),
    ("v0.9.0", "视图鉴权", "视图鉴权与启动自检", "M3", "", "09-v0.9.0-视图鉴权与启动自检"),
    ("v0.10.0", "模板渲染", "模板层权限渲染", "M3", "", "10-v0.10.0-模板层权限渲染"),
    ("v0.11.0", "动态菜单", "动态菜单树", "M3", "", "11-v0.11.0-动态菜单树"),
    ("v0.12.0", "角色继承", "角色继承（RBAC1）", "M4", "", "12-v0.12.0-角色继承RBAC1"),
    ("v0.13.0", "工单", "工单模块", "M5", "warn", "13-v0.13.0-工单模块"),
    ("v0.14.0", "数据权限", "数据权限", "M5", "bad", "14-v0.14.0-数据权限"),
    ("v0.15.0", "单条校验", "自定义范围与单条校验", "M5", "", "15-v0.15.0-自定义范围与单条校验"),
    ("v0.16.0", "缓存", "权限缓存", "M6", "", "16-v0.16.0-权限缓存"),
    ("v0.17.0", "审计", "审计日志", "M6", "", "17-v0.17.0-审计日志"),
    ("v0.18.0", "越权加固", "越权防护加固", "M6", "", "18-v0.18.0-越权防护加固"),
    ("v0.19.0", "测试", "测试套件与越权矩阵", "M6", "", "19-v0.19.0-测试套件"),
    ("v1.0.0", "完整版", "阶段一完整版", "M7", "", "20-v1.0.0-阶段一完整版"),
    ("v1.1.0", "DRF+JWT", "DRF 与 JWT", "M8", "warn", "21-v1.1.0-DRF与JWT"),
    ("v1.2.0", "内核复用", "API 权限复用", "M8", "acc", "22-v1.2.0-API权限复用"),
]

MILESTONES = {
    "M0": "文档", "M1": "地基", "M2": "RBAC0", "M3": "执行层", "M4": "RBAC1",
    "M5": "数据权限", "M6": "工程化", "M7": "完整版", "M8": "API 化",
}

UNSAFE = [  # 刻意留下的不安全中间态：(缺口所在 tag, 补上的 tag, 说明)
    ("v0.8.0", "v0.11.0", "菜单写死"),
    ("v0.13.0", "v0.14.0", "无数据权限"),
    ("v1.1.0", "v1.2.0", "API 无授权"),
]


def tag_href(root, fname):
    return f"{root}tags/{fname}.html"


# ------------------------------------------------------------------ 00 理论基础

def fig_blp(ctx):
    f = Fig(640, 232, "Bell-LaPadula：机密级主体可以向下读、向上写，不能向上读、向下写")
    levels = ["绝密", "机密", "秘密", "公开"]
    for i, name in enumerate(levels):
        y = 16 + i * 50
        f.rect(20, y, 600, 44, cls="zone" + (" acc" if i == 1 else ""), rx=6)
        f.text(40, y + 27, name, anchor="start", bold=True)
    subj = f.box(120, 71, 150, 34, "主体（机密级）", kind="acc")
    f.arrow([subj.right(), (520, 88)], head=False)
    f.circle(380, 88, 3.5)
    f.circle(520, 88, 3.5)
    f.text(380, 222, "读", bold=True)
    f.text(520, 222, "写", bold=True)
    f.arrow([(380, 88), (380, 40)], kind="bad", dashed=True)
    f.text(392, 34, "✕ no read up", anchor="start", cls="bad", fs=12)
    f.arrow([(380, 88), (380, 138)], kind="good")
    f.text(392, 142, "✓ 可读", anchor="start", cls="good", fs=12)
    f.arrow([(520, 88), (520, 40)], kind="good")
    f.text(532, 34, "✓ 可写", anchor="start", cls="good", fs=12)
    f.arrow([(520, 88), (520, 188)], kind="bad", dashed=True)
    f.text(532, 192, "✕ no write down", anchor="start", cls="bad", fs=12)
    return f.svg(), "规则一挡住「读上级」，规则二挡住「写下级」。后者防的是：机密级主体把读到的内容写进公开文件，信息就向下泄漏了。"


def fig_acl_vs_rbac(ctx):
    f = Fig(800, 300, "张三转岗：ACL 要改 3 条用户-权限直连，RBAC 只改 1 条用户-角色关系")
    users = ["张三", "李四", "王五", "赵六"]
    perms = ["查看工单", "新建工单", "编辑工单", "导出工单"]
    # 左：ACL
    f.text(190, 22, "ACL：用户直接连权限", bold=True)
    ub = [f.box(20, 44 + i * 52, 80, 34, u, kind="acc" if i == 0 else "") for i, u in enumerate(users)]
    pb = [f.box(250, 44 + i * 52, 110, 34, p) for i, p in enumerate(perms)]
    acl = {0: [0, 1, 2], 1: [0, 1, 2], 2: [0, 1, 2, 3], 3: [0, 1, 2, 3]}
    for u, ps in acl.items():
        for p in ps:
            f.arrow([ub[u].right(), pb[p].left()], kind="acc" if u == 0 else "mut", head=False,
                    width=2 if u == 0 else None)
    f.text(190, 268, "14 条用户-权限关系", cls="mut", fs=12)
    f.text(190, 288, "张三转岗：找出并改掉 3 条，漏一条就是隐患", cls="acc", fs=12)
    # 右：RBAC
    x0 = 420
    f.text(x0 + 180, 22, "RBAC：经由角色", bold=True)
    ub2 = [f.box(x0, 44 + i * 52, 70, 34, u, kind="acc" if i == 0 else "") for i, u in enumerate(users)]
    rb = [f.box(x0 + 130, 70, 90, 34, "客服专员"), f.box(x0 + 130, 174, 90, 34, "客服主管")]
    pb2 = [f.box(x0 + 270, 44 + i * 52, 90, 34, p) for i, p in enumerate(perms)]
    ur = {0: 0, 1: 0, 2: 1, 3: 1}
    for u, r in ur.items():
        f.arrow([ub2[u].right(), rb[r].left()], kind="acc" if u == 0 else "mut", head=False,
                width=2 if u == 0 else None)
    for r, ps in {0: [0, 1, 2], 1: [0, 1, 2, 3]}.items():
        for p in ps:
            f.arrow([rb[r].right(), pb2[p].left()], kind="mut", head=False)
    f.text(x0 + 180, 268, "4 条用户-角色 + 7 条角色-权限", cls="mut", fs=12)
    f.text(x0 + 180, 288, "张三转岗：只改 1 条用户-角色", cls="acc", fs=12)
    return f.svg(), "同样的授权结果，两种存法。RBAC 省下的不只是几条记录：人员流动只触及「用户-角色」这一层，角色-权限这一层保持稳定。"


def fig_rbac0(ctx):
    f = Fig(720, 250, "NIST RBAC0：用户经 UA 获得角色，角色经 PA 获得权限，会话激活用户角色的一个子集")
    u = f.box(30, 50, 120, 50, ["USERS", ("用户", {"fs": 12, "cls": "mut"})])
    r = f.box(300, 50, 120, 50, ["ROLES", ("角色", {"fs": 12, "cls": "mut"})], kind="acc")
    f.rect(540, 22, 160, 106, cls="bx")
    f.text(620, 44, "PRMS 权限", bold=True)
    f.box(552, 62, 58, 50, ["OPS", ("操作", {"fs": 11, "cls": "mut"})], fs=12)
    f.text(620, 92, "×", fs=16)
    f.box(630, 62, 58, 50, ["OBS", ("客体", {"fs": 11, "cls": "mut"})], fs=12)
    f.arrow([u.right(), r.left()], tail=True, label="UA 多对多")
    f.arrow([r.right(), (540, 75)], tail=True, label="PA 多对多")
    s = f.box(170, 176, 150, 46, ["SESSIONS 会话", ("本项目不实现", {"fs": 11, "cls": "mut"})],
              dashed=True)
    f.arrow([(90, 100), (90, 199), s.left()], dashed=True, kind="mut", label="用户开启会话", seg=1,
            lpos=(96, 150), lanchor="start")
    f.arrow([s.right(), (360, 199), (360, 100)], dashed=True, kind="mut")
    f.text(368, 160, "激活其中部分角色", anchor="start", cls="mut", fs=12)
    f.text(430, 200, "本项目：登录即全部角色生效", anchor="start", cls="mut", fs=12)
    return f.svg(), "实线是本项目实现的部分；虚线的会话与角色激活属于标准，但本项目不做（理由见第 5 章）。"


def fig_role_chain(ctx):
    f = Fig(720, 280, "角色继承：客服主管继承客服专员，客服专员继承普通员工，权限沿继承方向累积")
    cols = [(40, "普通员工", [("查看公告", True)]),
            (280, "客服专员", [("查看公告", False), ("查看工单", True), ("新建工单", True)]),
            (520, "客服主管", [("查看公告", False), ("查看工单", False), ("新建工单", False),
                               ("派单", True), ("导出工单", True)])]
    boxes = []
    for x, name, chips in cols:
        boxes.append(f.box(x, 20, 160, 40, name, kind="acc"))
        for i, (c, own) in enumerate(chips):
            f.box(x + 20, 76 + i * 30, 120, 24, c, fs=12, dashed=not own,
                  kind="" if own else "ghost")
    f.arrow([boxes[2].left(), boxes[1].right()], label="继承自")
    f.arrow([boxes[1].left(), boxes[0].right()], label="继承自")
    f.box(40, 244, 60, 22, "直接", fs=11)
    f.text(108, 259, "本角色直接授予", anchor="start", fs=12, cls="mut")
    f.box(240, 244, 60, 22, "继承", fs=11, dashed=True, kind="ghost")
    f.text(308, 259, "运行时沿继承链算出，不落库", anchor="start", fs=12, cls="mut")
    return f.svg(), "箭头指向被继承的角色，权限沿箭头的反方向累积：客服主管 = 自己的 2 个 + 客服专员的 2 个 + 普通员工的 1 个。"


def fig_nist_levels(ctx):
    f = Fig(720, 270, "NIST 四个层级：RBAC0 加角色继承得 RBAC1，加约束得 RBAC2，两者合一为 RBAC3；本项目停在 RBAC1 并补上数据范围")
    r3 = f.box(290, 18, 140, 46, ["RBAC3", ("继承 + 约束", {"fs": 11, "cls": "mut"})], kind="ghost",
               dashed=True)
    r1 = f.box(120, 108, 180, 54, ["RBAC1 角色层级", ("本项目：单继承 + 深度 5", {"fs": 11})],
               kind="acc")
    r2 = f.box(420, 108, 180, 54, ["RBAC2 约束", ("SoD 等，本项目不做", {"fs": 11, "cls": "mut"})],
               kind="ghost", dashed=True)
    r0 = f.box(290, 206, 140, 46, ["RBAC0 核心", ("用户 · 角色 · 权限", {"fs": 11, "cls": "mut"})])
    f.arrow([r0.top(-30), (r0.cx - 30, 185), (r1.cx, 185), r1.bottom()], label="+ 角色继承",
            seg=1, kind="acc")
    f.arrow([r0.top(30), (r0.cx + 30, 185), (r2.cx, 185), r2.bottom()], label="+ 约束",
            seg=1, kind="mut", dashed=True)
    f.arrow([r1.top(), (r1.cx, 41), r3.left()], kind="mut", dashed=True)
    f.arrow([r2.top(), (r2.cx, 41), r3.right()], kind="mut", dashed=True)
    ds = f.box(20, 206, 200, 46, ["+ 数据范围", ("标准之外，退化的 ABAC", {"fs": 11, "cls": "mut"})],
               kind="warn")
    f.arrow([ds.top(), (ds.cx, 162)], kind="warn", dashed=True)
    return f.svg(), "四层是递进关系。本项目 = RBAC1（受限层级）+ 数据范围，后者在 NIST 标准里没有位置（第 6 章）。"


def fig_two_routes(ctx):
    f = Fig(800, 300, "对象级权限随用户乘对象增长，数据范围只存一条规则并在查询时覆盖新数据")
    f.zone(10, 10, 380, 280, "路线 A · 对象级权限（django-guardian）")
    rows = ["alice · 工单#1 · change", "alice · 工单#2 · change", "bob · 工单#1 · view",
            "bob · 工单#2 · view", "…"]
    for i, r in enumerate(rows):
        f.box(40, 40 + i * 28, 210, 24, r, fs=11, anchor="start", kind="ghost" if r == "…" else "")
    f.text(145, 196, "80 张工单 × 6 用户 × 6 操作 = 2880 行", fs=12, cls="mut")
    nt = f.box(40, 222, 150, 34, "新建工单 #81", kind="warn")
    f.arrow([nt.right(), (290, 239), (290, 150), (255, 150)], kind="bad", label="再写 36 行授权",
            seg=1, lpos=(298, 200), lanchor="start")
    f.text(200, 276, "部门调整 → 全量重算", fs=12, cls="bad")

    f.zone(410, 10, 380, 280, "路线 B · 数据范围（本项目）")
    role = f.box(440, 44, 200, 44, ["Role 客服主管", ("data_scope = 2（本部门及以下）", {"fs": 11, "cls": "mut", "mono": False})],
                 kind="acc")
    tk = f.box(440, 160, 200, 44, ["Ticket 表", ("department_id 随工单存", {"fs": 11, "cls": "mut"})])
    f.arrow([role.bottom(), tk.top()], kind="acc", label="查询时翻译成 WHERE")
    f.text(540, 226, "WHERE department_id IN (/1/3/ 子树)", fs=11, mono=True, cls="acc")
    nt2 = f.box(660, 166, 110, 32, "新建工单 #81", kind="warn", fs=12)
    f.arrow([nt2.left(), tk.right()], kind="good")
    f.text(715, 218, "只写工单本身", fs=12, cls="good")
    f.text(600, 276, "新数据自动被规则覆盖，什么都不用补", fs=12, cls="good")
    return f.svg(), "判据只有一条：授权关系是被人指定的（左），还是被规则推导的（右）。"


# ------------------------------------------------------------------ 路线图

def fig_roadmap(ctx, arcs=True):
    root = ctx["root"]
    rh, top = 27, 30
    n = len(TAGS)
    W, H = 800, top + n * rh + 34
    f = Fig(W, H, "23 个 tag 的路线图：按里程碑分组，标出三个刻意留下的不安全中间态及其补上的位置",
            min_width=560)
    xs, xv, xn, xa = 150, 170, 262, 560
    f.text(xv, 16, "tag", anchor="start", fs=11, cls="mut")
    f.text(xn, 16, "内容（点击进入该 tag 指南）", anchor="start", fs=11, cls="mut")
    ypos = {}
    for i, (ver, short, full, ms, mark, fname) in enumerate(TAGS):
        y = top + i * rh + rh / 2
        ypos[ver] = y
    f.path(f"M{xs} {ypos['v0.0.1-docs']} L{xs} {ypos['v1.2.0']}", cls="ln mut")
    # 阶段分隔
    ysplit = (ypos["v1.0.0"] + ypos["v1.1.0"]) / 2
    f.path(f"M20 {ysplit} L{W - 20} {ysplit}", cls="ln mut", dashed=True)
    f.text(W - 24, ysplit - 6, "阶段一：模板渲染 ↑   阶段二：API 化 ↓", anchor="end", fs=11,
           cls="mut")
    for i, (ver, short, full, ms, mark, fname) in enumerate(TAGS):
        y = ypos[ver]
        kind = {"warn": "warn", "bad": "bad", "acc": "acc"}.get(mark, "")
        cnt = 0
        f.circle(xs, y, 6 if mark else 4.5, kind=kind or "plain"); cnt += 1
        f.text(xv, y + 4.5, ver, anchor="start", fs=12, mono=True); cnt += 1
        sym = {"warn": " ⚠", "bad": " 🔴", "acc": " 🎯"}.get(mark, "")
        f.text(xn, y + 4.5, full + sym, anchor="start", fs=13); cnt += 1
        if fname:
            f.rect(xv - 6, y - rh / 2 + 2, 380, rh - 4, cls="hit", rx=4); cnt += 1
            # hit 放最后会盖住文字，挪到最前
            hit = f.parts.pop()
            f.parts.insert(len(f.parts) - (cnt - 1), hit)
            f.link(tag_href(root, fname), cnt)
    # 里程碑
    groups = {}
    for ver, *_rest in TAGS:
        ms = _rest[2]
        groups.setdefault(ms, []).append(ypos[ver])
    for ms, ys in groups.items():
        y1, y2 = min(ys), max(ys)
        if y2 > y1:
            f.path(f"M{xs - 30} {y1 - 8} L{xs - 36} {y1 - 8} L{xs - 36} {y2 + 8} L{xs - 30} {y2 + 8}",
                   cls="ln mut")
        cy = (y1 + y2) / 2
        if y2 > y1:
            f.text(xs - 44, cy - 2, ms, anchor="end", fs=12, bold=True)
            f.text(xs - 44, cy + 13, MILESTONES[ms], anchor="end", fs=11, cls="mut")
        else:
            f.text(xs - 20, cy + 4, f"{ms} {MILESTONES[ms]}", anchor="end", fs=11, cls="mut")
    if arcs:
        for a, b, what in UNSAFE:
            y1, y2 = ypos[a], ypos[b]
            f.arrow([(xa, y1), (xa + 26, y1), (xa + 26, y2), (xa, y2)], kind="warn", dashed=True)
            f.text(xa + 34, (y1 + y2) / 2 + 4, f"{what} → {b} 补上", anchor="start", fs=12,
                   cls="warn")
    return f.svg(), "⚠ 是刻意留下的不安全中间态（右侧虚线指向补上它的 tag），🔴 是最容易写出安全漏洞的 tag，🎯 是整个架构的检验点。"


def fig_roadmap_plain(ctx):
    return fig_roadmap(ctx, arcs=True)


def fig_tag_strip(ctx):
    """每份 tag 指南顶部的进度条。"""
    root, cur = ctx["root"], ctx.get("tag")
    tags = [t for t in TAGS if t[5]]
    W, H = 760, 78
    f = Fig(W, H, f"学习进度：当前 {cur}，共 22 个 tag", min_width=520)
    x0, step, y = 30, 32.5, 34
    f.path(f"M{x0} {y} L{x0 + step * (len(tags) - 1)} {y}", cls="ln mut")
    ms_x = {}
    for i, (ver, short, full, ms, mark, fname) in enumerate(tags):
        x = x0 + i * step
        ms_x.setdefault(ms, []).append(x)
        is_cur = ver == cur
        kind = "acc" if is_cur else ({"warn": "warn", "bad": "bad", "acc": "acc"}.get(mark, "plain"))
        f.rect(x - 14, y - 16, 28, 32, cls="hit", rx=4)
        f.circle(x, y, 8 if is_cur else 4.5, kind=kind + (" cur" if is_cur else ""))
        f.link(tag_href(root, fname), 2)
        if is_cur:
            anchor = "start" if i < 3 else ("end" if i > len(tags) - 4 else "middle")
            f.text(x, y - 16, f"{ver} {short}", fs=12, bold=True, cls="acc", anchor=anchor)
    for ms, xsl in ms_x.items():
        a, b = min(xsl), max(xsl)
        if b > a:
            f.path(f"M{a - 6} 56 L{b + 6} 56", cls="ln mut")
        f.text((a + b) / 2, 72, ms, fs=11, cls="mut")
    return f.svg(), None


def fig_learning_loop(ctx):
    f = Fig(810, 196, "推荐学习流程：读指南、做思考题、按契约实现、自测、git diff 对比、延伸思考；卡住时才展开渐进提示")
    steps = [("读指南", "先不看提示"), ("思考题", "不要跳过"), ("按契约实现", "契约照抄"),
             ("自测清单", "跑命令和用例"), ("git diff", "逐条走对比点"), ("延伸思考", "开放问题")]
    bs = []
    for i, (a, b) in enumerate(steps):
        x = 20 + i * 132
        bs.append(f.box(x, 24, 110, 50, [a, (b, {"fs": 11, "cls": "mut"})],
                        kind="acc" if i in (1, 4) else ""))
    for i in range(len(bs) - 1):
        f.arrow([bs[i].right(), bs[i + 1].left()])
    hint = f.box(bs[2].x - 10, 128, 130, 46, ["渐进提示", ("卡住了才展开", {"fs": 11, "cls": "mut"})],
                 dashed=True, kind="ghost")
    f.arrow([bs[2].bottom(-25), (bs[2].cx - 25, 128)], kind="mut", dashed=True, label="卡住",
            lpos=(bs[2].cx - 32, 106), lanchor="end")
    f.arrow([(bs[2].cx + 25, 128), bs[2].bottom(25)], kind="mut", dashed=True, label="继续写",
            lpos=(bs[2].cx + 32, 106), lanchor="start")
    return f.svg(), "两个高亮步骤是收益最大的：动手前的思考题，和写完后对着 diff 找差异。"


# ------------------------------------------------------------------ 02 设计文档

def fig_architecture(ctx):
    f = Fig(760, 420, "分层架构：Web 与 API 两个薄适配器调用同一个不认识 HTTP 的权限内核")
    f.zone(20, 14, 720, 130, "表现层（薄适配器）")
    web = f.box(50, 42, 300, 86, ["Web · Django 模板 + Tailwind",
                                  ("@require_perm · PermRequiredMixin", {"fs": 12, "mono": True}),
                                  ("{% if 'x' in perms %}", {"fs": 12, "mono": True, "cls": "mut"})])
    api = f.box(410, 42, 300, 86, ["API · DRF + JWT（阶段二）",
                                   ("HasPerm · ScopedQuerysetMixin", {"fs": 12, "mono": True}),
                                   ("/api/v1/auth/profile", {"fs": 12, "mono": True, "cls": "mut"})])
    f.path("M20 166 L740 166", cls="ln bad", dashed=True)
    f.text(380, 160, "HTTP 边界：上面认识 request，下面不认识", fs=12, cls="bad", halo=True)
    k = f.box(130, 190, 500, 118, [
        ("权限内核 apps/rbac/services.py", {"bold": True}),
        ("get_user_perm_codes(user) → set[str]", {"fs": 12, "mono": True}),
        ("user_has_perm(user, code) → bool", {"fs": 12, "mono": True}),
        ("build_scope_q(user, cfg) → Q | None", {"fs": 12, "mono": True}),
        ("get_user_menu_tree(user) · expand_roles(roles)", {"fs": 12, "mono": True}),
    ], kind="acc")
    f.arrow([(200, 128), (200, 190)], tail=True, label="False → 403.html", lpos=(208, 184),
            lanchor="start", fs=11)
    f.arrow([(560, 128), (560, 190)], tail=True, label="False → 403 JSON", lpos=(568, 184),
            lanchor="start", fs=11)
    d = f.box(60, 350, 300, 52, ["数据层", ("Department · Role · Permission · UserRole · Ticket",
                                              {"fs": 11, "cls": "mut"})])
    c = f.box(400, 350, 300, 52, ["缓存层", ("L1 请求级 + L2 Django cache（版本号）",
                                               {"fs": 11, "cls": "mut"})])
    f.arrow([(240, 308), (240, 350)], label="ORM 查询", fs=11)
    f.arrow([(520, 308), (520, 350)], label="按版本号读写", fs=11)
    return f.svg(), "两个适配器只做翻译：把 request.user 交给内核，把 False 翻译成 403 页面或 403 JSON。权限怎么算只存在于中间那一个模块里。"


def fig_deps(ctx):
    f = Fig(720, 220, "应用依赖严格单向：tickets 和 audit 依赖 rbac，rbac 依赖 accounts，accounts 依赖 common；禁止反向")
    t = f.box(20, 28, 100, 38, "tickets")
    a = f.box(20, 98, 100, 38, "audit")
    r = f.box(220, 62, 110, 40, "rbac", kind="acc")
    ac = f.box(410, 62, 110, 40, "accounts")
    c = f.box(590, 62, 110, 40, "common")
    f.arrow([t.right(), (170, t.cy), (170, r.cy)], head=False)
    f.arrow([a.right(), (170, a.cy), (170, r.cy)], head=False)
    f.arrow([(170, r.cy), r.left()])
    f.arrow([r.right(), ac.left()], label="Department", fs=11)
    f.text(365, 50, "ADR-016 的妥协", fs=11, cls="mut")
    f.arrow([ac.right(), c.left()])
    f.arrow([(170, a.cy), (170, 190), (c.cx, 190), c.bottom()], kind="mut", label="共享基类",
            seg=1, fs=11)
    f.curve((ac.cx, ac.b), (ac.cx, 150), (r.cx, 150), (r.cx, r.b), kind="bad", dashed=True)
    f.text((ac.cx + r.cx) / 2, 158, "✕ 禁止反向 import（NFR-8）", fs=12, cls="bad", halo=True)
    return f.svg(), "唯一一处具体类耦合是 rbac 直接 import accounts.Department，而且被收敛到 get_user_dept_ids() 一个函数里。"


def fig_dept_path(ctx):
    f = Fig(800, 300, "部门子树查询是一次 path 前缀匹配；尾斜杠是分隔符，去掉它 /1/31/ 会被误判为 /1/3/ 的后代")

    def node(x, y, name, path, kind=""):
        return f.box(x, y, 112, 46, [name, (path, {"fs": 11, "mono": True, "cls": "mut"})],
                     kind=kind)

    f.rect(12, 96, 248, 170, cls="zone acc", rx=10)
    f.text(24, 286, "客服部子树 = path 以 /1/3/ 开头", anchor="start", fs=12, cls="acc")
    root = node(150, 14, "总公司", "/1/")
    cs = node(20, 110, "客服部", "/1/3/", "acc")
    tech = node(160, 110, "技术部", "/1/4/")
    law = node(290, 110, "法务部", "/1/31/", "warn")
    g1 = node(20, 206, "一组", "/1/3/7/", "acc")
    g2 = node(140, 206, "二组", "/1/3/8/", "acc")
    for ch in (cs, tech, law):
        f.elbow_down(root, ch, mid=88)
    for ch in (g1, g2):
        f.elbow_down(cs, ch, mid=184)

    x0 = 440
    f.text(x0, 30, "filter(path__startswith=…)", anchor="start", fs=13, mono=True, bold=True)
    f.text(630, 58, "'/1/3/'", fs=12, mono=True, cls="good")
    f.text(730, 58, "'/1/3'", fs=12, mono=True, cls="bad")
    f.text(630, 74, "带尾斜杠", fs=11, cls="mut")
    f.text(730, 74, "不带", fs=11, cls="mut")
    rows = [("/1/3/", True, True), ("/1/3/7/", True, True), ("/1/3/8/", True, True),
            ("/1/31/", False, True), ("/1/4/", False, False)]
    for i, (p, a, b) in enumerate(rows):
        y = 92 + i * 34
        wrong = a != b
        f.rect(x0 - 8, y, 350, 30, cls="zone" + (" bad" if wrong else ""), rx=4)
        f.text(x0 + 4, y + 20, p, anchor="start", fs=12, mono=True)
        f.text(630, y + 20, "✓ 命中" if a else "—", fs=12, cls="good" if a else "mut")
        f.text(730, y + 20, ("✓ 命中" if b else "—") if not wrong else "✕ 误中", fs=12,
               cls="bad" if wrong else ("good" if b else "mut"))
    return f.svg(), "一条 LIKE '/1/3/%' 取出整棵子树并包含自身，这是选路径枚举的全部理由。代价是 path 冗余：只能由 save() 维护。"


def fig_perm_tree(ctx):
    f = Fig(800, 270, "权限点与菜单合表：目录和菜单节点渲染为侧边栏，按钮节点渲染为页面按钮，都是同一棵权限树")
    cat = f.box(20, 98, 150, 56, ["📁 工单管理", ("catalog · code = None", {"fs": 11, "mono": True, "cls": "mut"})])
    menu = f.box(220, 98, 200, 56, ["📄 工单列表", ("ticket:ticket:view", {"fs": 11, "mono": True}),
                                    ], kind="acc")
    btns = [("新建", "create"), ("编辑", "update"), ("删除", "delete"), ("派单", "assign"),
            ("导出", "export")]
    for i, (n, a) in enumerate(btns):
        b = f.box(490, 16 + i * 44, 250, 34, [(f"🔘 {n}  ticket:ticket:{a}", {"fs": 12})])
        f.arrow([menu.right(), (455, menu.cy), (455, b.cy), b.left()], head=False, kind="mut")
    f.arrow([cat.right(), menu.left()], head=False)
    f.text(455, 250, "", fs=1)
    f.path("M20 184 L420 184", cls="ln acc")
    f.text(220, 204, "侧边栏：catalog 分组 + menu 页面（menu 带 url_name、icon）", fs=12, cls="acc")
    f.path("M490 240 L740 240", cls="ln acc")
    f.text(615, 260, "页面按钮：每个都要配服务端 @require_perm", fs=12, cls="acc")
    return f.svg(), "管理员给角色勾权限时面对的就是这一棵树，勾一次同时决定「看得见哪些菜单」和「能点哪些按钮」。"


def fig_inherit_semantics(ctx):
    f = Fig(780, 270, "同一条数据 客服主管.parent = 客服专员，两种读法的权限流向相反")
    f.box(250, 12, 280, 34, "Role(客服主管).parent = 客服专员", fs=13, kind="warn")
    for x0, title, good in ((20, "读法一：parent = 被继承者（本项目）", True),
                            (400, "读法二：parent = 组织上级", False)):
        f.zone(x0, 62, 360, 196, title, kind="" if good else "")
        zy = f.box(x0 + 24, 104, 120, 40, "客服专员")
        zg = f.box(x0 + 216, 104, 120, 40, "客服主管")
        if good:
            f.arrow([zy.right(), zg.left()], kind="good", label="权限流向", width=2)
            f.box(x0 + 186, 170, 160, 50, ["客服主管拥有", ("查看 新建 + 派单 导出", {"fs": 12})],
                  kind="good")
            f.text(x0 + 180, 244, "主管 ⊇ 专员 ✓", fs=12, cls="good")
        else:
            f.arrow([zg.left(), zy.right()], kind="bad", label="权限流向", width=2)
            f.box(x0 + 14, 170, 160, 50, ["客服专员拥有", ("查看 新建 + 派单 导出", {"fs": 12})],
                  kind="bad")
            f.text(x0 + 180, 244, "专员拿到了主管的派单权 ✕", fs=12, cls="bad")
    return f.svg(), "两种实现都「说得通」，结果却相反。本项目把字段直接命名为 inherits_from，让字段名本身说明方向。"


def fig_scope_coverage(ctx):
    f = Fig(800, 214, "五种 data_scope 在同一棵部门树上覆盖的范围；张三在客服部")
    panels = [("ALL", "1 全部", "all"), ("DEPT_AND_BELOW", "2 本部门及以下", "sub"),
              ("DEPT_ONLY", "3 仅本部门", "self"), ("SELF_ONLY", "4 仅本人", "me"),
              ("CUSTOM", "5 自定义[市场部]", "custom")]
    for i, (code, name, mode) in enumerate(panels):
        x0 = 10 + i * 158
        f.zone(x0, 8, 150, 198)
        f.text(x0 + 75, 28, name, fs=12, bold=True)
        f.text(x0 + 75, 44, code, fs=10, mono=True, cls="mut")
        cov = {
            "all": {"总公司", "客服部", "市场部", "一组", "二组"},
            "sub": {"客服部", "一组", "二组"},
            "self": {"客服部"},
            "me": set(),
            "custom": {"市场部"},
        }[mode]

        def nd(x, y, n):
            label = n + ("★" if n == "客服部" else "")
            return f.box(x, y, 52 if n != "总公司" else 60, 24, label, fs=11,
                         kind="acc" if n in cov else "ghost", rx=4)

        r = nd(x0 + 45, 58, "总公司")
        cs = nd(x0 + 14, 104, "客服部")
        mk = nd(x0 + 84, 104, "市场部")
        g1 = nd(x0 + 4, 150, "一组")
        g2 = nd(x0 + 60, 150, "二组")
        for c in (cs, mk):
            f.elbow_down(r, c, kind="mut")
        for c in (g1, g2):
            f.elbow_down(cs, c, kind="mut")
        if mode == "me":
            f.box(x0 + 22, 178, 106, 22, "creator = 张三", fs=11, kind="acc", rx=4)
    return f.svg(), "高亮的节点就是该范围能看到的工单所属部门。「仅本人」不看部门，看工单的 creator；「自定义」勾选的部门含各自子树。★ 是张三所在部门。"


def fig_union(ctx):
    f = Fig(780, 270, "张三有 SELF_ONLY 和 CUSTOM[市场部] 两个角色：取最宽枚举会丢掉市场部，OR 并集才正确")
    for x0, title, good in ((10, "✕ 取「最宽」枚举：min(4, 5) = 4", False),
                            (400, "✓ 真并集：各角色的 Q 用 OR 连起来", True)):
        f.zone(x0, 10, 370, 250)
        f.text(x0 + 185, 34, title, fs=13, bold=True, cls="good" if good else "bad")
        f.rect(x0 + 20, 50, 330, 150, cls="bx ghost", rx=8)
        f.text(x0 + 30, 68, "全部工单", anchor="start", fs=11, cls="mut")
        f.ellipse(x0 + 110, 130, 72, 44, kind="acc")
        f.lines(x0 + 110, 130, ["角色 A", ("creator = 张三", {"fs": 11})], fs=12)
        f.ellipse(x0 + 260, 130, 72, 44, kind="acc" if good else "ghost", dashed=not good)
        f.lines(x0 + 260, 130, ["角色 B", ("市场部子树", {"fs": 11})], fs=12,)
        if good:
            f.text(x0 + 185, 222, "Q(creator=张三) | Q(department__in=市场部树)", fs=11,
                   mono=True, cls="good")
            f.text(x0 + 185, 244, "两个角色授予的数据都能看到", fs=12, cls="good")
        else:
            f.text(x0 + 260, 190, "被丢掉", fs=12, cls="bad")
            f.text(x0 + 185, 222, "SELF_ONLY(4) 比 CUSTOM(5) 编号小 → 只剩 A", fs=12, cls="bad")
            f.text(x0 + 185, 244, "违反「多角色权限取并集」", fs=12, cls="bad")
    return f.svg(), "编号从宽到窄排，min() 看起来很顺手，但 CUSTOM 和其他范围不存在包含关系，只能求并集。短路只用于 ALL。"


def fig_implicit(ctx):
    f = Fig(800, 290, "显式 for_user(user) 在每个调用点都可见；隐式 thread-local 过滤的行为取决于调用上下文")
    f.zone(10, 10, 370, 270, "显式：.for_user(user)（本项目）")
    calls = [("视图", "Ticket.objects.for_user(request.user)"),
             ("Celery 任务", "Ticket.objects.for_user(task_user)"),
             ("管理命令", "Ticket.objects.all()  ← 一眼可见未过滤")]
    for i, (who, code) in enumerate(calls):
        y = 42 + i * 64
        f.text(26, y + 14, who, anchor="start", fs=12, bold=True)
        f.box(26, y + 22, 330, 30, [(code, {"fs": 11, "mono": True})],
              kind="good" if i < 2 else "warn", anchor="start")
    f.text(195, 254, "grep for_user 能列出所有接入点，", fs=12, cls="good")
    f.text(195, 272, "grep objects.all() 能找出所有绕过点", fs=12, cls="good")

    f.zone(410, 10, 380, 270, "隐式：默认 Manager 读 thread-local")
    mgr = f.box(640, 90, 140, 110, ["get_queryset()", ("读 thread-local", {"fs": 11, "cls": "mut"}),
                                    ("current_user", {"fs": 11, "mono": True, "cls": "mut"})])
    ctxs = [("视图", "张三", "good"), ("Celery / 命令", "空 → 全集？空集？", "bad"),
            ("async 视图", "可能是别的请求的用户", "bad")]
    for i, (who, got, kind) in enumerate(ctxs):
        y = 46 + i * 74
        b = f.box(426, y, 110, 44, [who, ("objects.all()", {"fs": 10, "mono": True, "cls": "mut"})],
                  fs=12)
        f.arrow([b.right(), (mgr.l, mgr.y + 20 + i * 35)], kind=kind)
        f.text(426, y + 60, got, anchor="start", fs=11, cls=kind)
    f.text(600, 272, "读代码时无法判断一个查询被没被过滤", fs=12, cls="bad")
    return f.svg(), "隐式方案省掉的是一次调用，失去的是「看得见」：同一行 Ticket.objects.all() 在不同上下文返回不同结果。"


def fig_invalidation(ctx):
    f = Fig(800, 290, "逐 key 删除要沿继承链反查受影响用户，任一步写漏就会让撤销的权限继续生效；版本号法一次让全部旧 key 不可达")
    f.zone(10, 10, 380, 270, "方案 a · 逐 key 删除")
    steps = ["改「客服专员」的权限", "递归找所有继承它的角色", "找这些角色的全部用户", "逐个 cache.delete(key)"]
    prev = None
    for i, s in enumerate(steps):
        b = f.box(40, 40 + i * 58, 200, 38, s, fs=12, kind="warn" if i == 1 else "")
        if prev:
            f.arrow([prev.bottom(), b.top()])
        prev = b
    f.box(258, 90, 118, 92, ["漏掉继承链", "或反查写错", ("→ 权限已撤销", {"cls": "bad"}),
                             ("　仍然生效", {"cls": "bad"})], kind="bad", fs=12)
    f.arrow([(240, 117), (258, 117)], kind="bad", dashed=True)

    f.zone(410, 10, 380, 270, "方案 b · 全局版本号（本项目）")
    v = f.box(440, 40, 320, 40, [("bump_version()：rbac:version  7 → 8", {"mono": True, "fs": 12})],
              kind="acc")
    old = ["rbac:perms:3:7", "rbac:perms:42:7", "rbac:perms:57:7"]
    for i, k in enumerate(old):
        f.box(440, 104 + i * 34, 150, 28, [(k, {"mono": True, "fs": 11, "cls": "mut"})],
              kind="ghost", dashed=True, rx=4)
    f.text(515, 222, "不再被读取，等 TTL 淘汰", fs=11, cls="mut")
    nk = f.box(620, 138, 150, 44, [("rbac:perms:42:8", {"mono": True, "fs": 11}),
                                   ("下次请求重算写入", {"fs": 11})], kind="good", rx=4)
    f.arrow([(600, 152), nk.left(-8)], kind="good")
    f.text(600, 262, "不需要知道谁受影响，所以不会漏", fs=12, cls="good")
    return f.svg(), "失效漏了是安全问题，失效多了只是性能问题。版本号法用后者换前者。"


def fig_cache_levels(ctx):
    f = Fig(800, 250, "权限码解析路径：超管短路，然后依次查 L1 请求级缓存、L2 Django cache、数据库；L1 和 L2 都用版本号校验")
    s = f.box(10, 96, 140, 50, [("get_user_perm_codes", {"fs": 11, "mono": True}),
                                ("(user)", {"fs": 11, "mono": True})], fs=12)
    su = f.box(175, 96, 95, 50, ["is_superuser?"], fs=12)
    allp = f.box(172, 14, 100, 38, [("ALL_PERMS 哨兵", {"fs": 11})], kind="good")
    l1 = f.box(305, 96, 140, 50, ["L1 请求级", ("user._rbac_perm_cache", {"fs": 10, "mono": True, "cls": "mut"})],
               fs=12, kind="acc")
    l2 = f.box(495, 96, 140, 50, ["L2 Django cache", ("rbac:perms:{uid}:{v}", {"fs": 10, "mono": True, "cls": "mut"})],
               fs=12, kind="acc")
    db = f.box(685, 96, 105, 50, ["数据库", ("4~5 次查询", {"fs": 11, "cls": "mut"})], fs=12)
    f.arrow([s.right(), su.left()])
    f.arrow([su.top(), allp.bottom()], kind="good", label="是", fs=11)
    f.arrow([su.right(), l1.left()], label="否", fs=11)
    f.arrow([l1.right(), l2.left()], label="未命中", fs=11)
    f.arrow([l2.right(), db.left()], label="未命中", fs=11)
    f.arrow([db.bottom(), (db.cx, 176), (l2.cx + 30, 176), (l2.cx + 30, l2.b)], kind="mut",
            dashed=True, label="回填", seg=1, fs=11)
    f.arrow([(l2.cx - 30, l2.b), (l2.cx - 30, 176), (l1.cx + 30, 176), (l1.cx + 30, l1.b)],
            kind="mut", dashed=True, label="回填 (v, codes)", seg=1, fs=11)
    ver = f.box(330, 202, 270, 34, [("rbac:version = v", {"mono": True, "fs": 12})], kind="warn")
    f.arrow([(ver.l + 20, ver.t), (ver.l + 20, 190), (l1.cx - 30, 190), (l1.cx - 30, l1.b)],
            kind="warn", seg=2, label="L1 比对版本", lpos=(l1.cx - 36, 170), lanchor="end", fs=11)
    return f.svg(), "L1 也必须带版本号：bump_version() 动不了已经挂在 user 对象上的缓存，同一请求里先改后读就会读到旧值。"


def fig_er(ctx):
    f = Fig(800, 510, "数据模型：箭头是外键，从持有外键的表指向被引用的表；三个区域对应 accounts、rbac、tickets/audit 三个应用")
    A, B, C = 40, 315, 590
    W = 170

    def ent(x, y, name, fields, kind=""):
        h = 34 + 18 * len(fields)
        f.rect(x, y, W, h, cls="bx " + kind)
        f.text(x + 12, y + 22, name, anchor="start", bold=True, fs=13)
        f.path(f"M{x} {y + 31} L{x + W} {y + 31}", cls="ln mut")
        for i, fl in enumerate(fields):
            f.text(x + 12, y + 48 + i * 18, fl, anchor="start", fs=11, mono=True,
                   cls="" if "→" in fl or fl.startswith("*") else "mut")
        return Box(x, y, W, h)

    # 区域
    f.rect(22, 30, 480, 120, cls="zone", rx=10)
    f.text(495, 144, "accounts 组织域", anchor="end", fs=12, cls="mut", bold=True)
    f.path(f"M22 196 L502 196 L502 356 L782 356 L782 486 L22 486 Z", cls="zone acc")
    f.text(34, 214, "", fs=1)
    f.text(34, 478, "rbac 授权域", anchor="start", fs=12, cls="acc", bold=True)
    f.rect(572, 30, 210, 300, cls="zone", rx=10)
    f.text(772, 24, "tickets / audit", anchor="end", fs=12, cls="mut", bold=True)

    dep = ent(A, 42, "Department", ["parent → self", "path  /1/3/7/", "depth"])
    usr = ent(B, 42, "User", ["department →", "is_superuser"])
    tk = ent(C, 42, "Ticket", ["creator →", "assignee →", "department →"])
    rd = ent(A, 220, "RoleDepartment", ["role →", "department →"])
    ur = ent(B, 220, "UserRole", ["user →", "role →", "granted_by"])
    al = ent(C, 212, "AuditLog", ["actor →", "action", "detail (快照)"])
    role = ent(A, 380, "Role", ["inherits_from → self", "data_scope = 4"], kind="acc")
    rp = ent(B, 380, "RolePermission", ["role →", "permission →"])
    pm = ent(C, 372, "Permission", ["parent → self", "code", "perm_type"], kind="acc")

    f.arrow([(usr.l, 100), (dep.r, 100)], label="department", fs=11)
    f.arrow([(tk.l, 88), (usr.r, 88)], label="creator", fs=11)
    f.arrow([(tk.l, 118), (usr.r, 118)], label="assignee", fs=11, loff=-12)
    f.arrow([(tk.cx, tk.t), (tk.cx, 14), (dep.cx, 14), (dep.cx, dep.t)], label="department",
            seg=1, fs=11)
    f.arrow([(al.cx, al.t), (al.cx, 170), (460, 170), (460, usr.b)], label="actor", seg=1, fs=11)
    f.arrow([(400, ur.t), (400, usr.b)], label="user", fs=11)
    f.arrow([(rd.cx, rd.t), (rd.cx, dep.b)], label="department", fs=11)
    f.arrow([(rd.cx, rd.b), (rd.cx, role.t)], label="role", fs=11)
    f.arrow([(350, ur.b), (350, 350), (190, 350), (190, role.t)], label="role", seg=1, fs=11)
    f.arrow([(rp.l, 425), (role.r, 425)], label="role", fs=11)
    f.arrow([(rp.r, 425), (pm.l, 425)], label="permission", fs=11)
    # 自引用
    for b, side, y in ((dep, "r", 62), (pm, "r", 392), (role, "l", 400)):
        if side == "r":
            x = b.r
            f.arrow([(x, y), (x + 14, y), (x + 14, y + 22), (x, y + 22)], fs=11)
        else:
            x = b.l
            f.arrow([(x, y), (x - 14, y), (x - 14, y + 22), (x, y + 22)], fs=11)
    return f.svg(), "Role 与 Permission 各有一条自引用：继承链和权限树。RolePermission 只存直接授予，继承结果不落库。"


def fig_expand_roles(ctx):
    f = Fig(760, 250, "expand_roles：从张三的两个直接角色向上展开祖先，第二条链走到已访问的普通员工时剪枝")
    z = f.box(20, 88, 76, 44, "张三", kind="warn")
    m = f.box(150, 36, 110, 40, "客服主管", kind="acc")
    q = f.box(150, 142, 110, 40, "质检员", kind="acc")
    s = f.box(340, 36, 110, 40, "客服专员", kind="acc")
    e = f.box(540, 88, 110, 40, "普通员工", kind="acc")
    f.arrow([z.right(-8), (120, z.cy - 8), (120, m.cy), m.left()], label="直接角色", seg=1,
            lpos=(112, 70), lanchor="end", fs=11)
    f.arrow([z.right(8), (120, z.cy + 8), (120, q.cy), q.left()], seg=1)
    f.arrow([m.right(), s.left()], label="继承自", fs=11)
    f.arrow([s.right(), (500, s.cy), (500, e.cy - 8), e.left(-8)], label="继承自", seg=0,
            fs=11)
    f.arrow([q.right(), (500, q.cy), (500, e.cy + 8), e.left(8)], kind="warn", dashed=True, seg=0,
            label="已在 result 中 → break", fs=11)
    f.box(150, 204, 500, 34, [("result = {客服主管, 客服专员, 普通员工, 质检员}", {"fs": 12})],
          kind="good")
    return f.svg(), "visited（即 result）同时防环和去重：即使数据库里被人绕过 clean() 写进了环，展开也不会死循环。"


def fig_scope_flow(ctx):
    f = Fig(780, 600, "build_scope_q 的控制流：四处默认拒绝都返回空集 Q(pk__in=[])，只有超管和 ALL 返回 None")
    X, Wd = 160, 280
    cx = X + Wd / 2
    RX = 472

    def deny(y, n, why):
        return f.box(RX, y, 290, 42, [(f"return Q(pk__in=[])  {n}", {"mono": True, "fs": 12}),
                                      (why, {"fs": 11})], kind="bad")

    def none(y, why):
        return f.box(RX, y, 290, 42, [("return None", {"mono": True, "fs": 12}),
                                      (why, {"fs": 11})], kind="acc")

    n1 = f.box(X, 18, Wd, 42, "已登录 且 is_active？")
    d1 = deny(18, "①", "匿名 / 已禁用")
    f.arrow([n1.right(), d1.left()], label="否", fs=11, lcls="bad")
    n2 = f.box(X, 90, Wd, 42, "is_superuser？")
    f.arrow([n1.bottom(), n2.top()], label="是", fs=11)
    s2 = none(90, "超管不过滤")
    f.arrow([n2.right(), s2.left()], label="是", fs=11)
    n3 = f.box(X, 162, Wd, 42, [("roles = expand_roles(直接角色)", {"fs": 12}), ("为空？", {"fs": 12})])
    f.arrow([n2.bottom(), n3.top()], label="否", fs=11)
    d2 = deny(162, "②", "无任何角色（最常见也最危险）")
    f.arrow([n3.right(), d2.left()], label="是", fs=11, lcls="bad")

    f.zone(X - 30, 226, Wd + 60, 206, "for role in roles")
    n4 = f.box(X, 252, Wd, 40, "scope == ALL？")
    f.arrow([n3.bottom(), n4.top()], label="否", fs=11)
    s4 = none(252, "短路：最宽范围")
    f.arrow([n4.right(), s4.left()], label="是", fs=11)
    n5 = f.box(X, 316, Wd, 46, [("按 scope 翻译为 sub", {"fs": 12}),
                                ("本部门 / 本部门及以下 / 本人 / 自定义", {"fs": 11, "cls": "mut"})])
    f.arrow([n4.bottom(), n5.top()], label="否", fs=11)
    d4 = f.box(RX, 316, 290, 46, [("get_user_dept_ids → set()  ④", {"mono": True, "fs": 12}),
                                  ("无部门：sub 是空集而不是全集", {"fs": 11})], kind="bad")
    f.arrow([n5.right(), d4.left()], kind="bad", dashed=True, label="部门类", fs=11)
    n6 = f.box(X, 384, Wd, 36, [("q |= sub；matched = True", {"mono": True, "fs": 12})])
    f.arrow([n5.bottom(), n6.top()])
    f.arrow([n6.left(), (X - 16, n6.cy), (X - 16, n4.cy), n4.left()], kind="mut",
            label="下一个 role", lpos=(X - 22, 300), lanchor="end", fs=11)
    f.arrow([(n5.l, n5.cy - 8), (X - 16, n5.cy - 8)], head=False, kind="mut", dashed=True)
    f.text(X - 20, n5.cy - 14, "不可识别 → continue", anchor="end", fs=11, cls="mut")

    n7 = f.box(X, 458, Wd, 40, "matched？")
    f.arrow([(cx, 432), n7.top()], label="循环结束", fs=11)
    d3 = deny(458, "③", "所有 scope 都不可识别（脏数据）")
    f.arrow([n7.right(), d3.left()], label="否", fs=11, lcls="bad")
    n8 = f.box(X, 530, Wd, 50, [("q &= extra_q(user)（若有）", {"mono": True, "fs": 12}),
                                ("return q", {"mono": True, "fs": 12})], kind="good")
    f.arrow([n7.bottom(), n8.top()], label="是", fs=11)
    return f.svg(), "红框是四处默认拒绝，在正常使用中几乎不会触发，所以每一处都要有自己的测试用例。把其中任何一处写成 Q()，含义就从「空集」变成「全集」。"


def fig_menu_prune(ctx):
    f = Fig(780, 306, "菜单树自底向上构建：先找出有权限的菜单，再沿 parent 保留祖先目录；没有任何可见后代的目录不渲染")
    f.text(20, 20, "一次查询取出全部 catalog / menu 节点", anchor="start", fs=12, cls="mut")
    rows = [(0, "📁 系统管理", None, True), (1, "📄 用户管理", True, True),
            (1, "📄 角色管理", False, False), (1, "📄 部门管理", False, False),
            (0, "📁 工单管理", None, True), (1, "📄 工单列表", True, True),
            (0, "📁 审计", None, False), (1, "📄 审计日志", False, False)]
    ys = []
    for i, (lvl, name, has, keep) in enumerate(rows):
        y = 34 + i * 30
        x = 40 + lvl * 34
        ys.append((x, y))
        f.box(x, y, 150, 24, [(name, {"fs": 12})], kind="acc" if keep else "ghost",
              dashed=not keep, anchor="start", pad=8, rx=4)
        if has is True:
            f.text(x + 160, y + 17, "✓ code in codes", anchor="start", fs=11, cls="good")
        elif has is False:
            f.text(x + 160, y + 17, "✕ 无权限", anchor="start", fs=11, cls="mut")
    for child, parent in ((1, 0), (5, 4)):
        (xc, yc), (xp, yp) = ys[child], ys[parent]
        f.arrow([(xc, yc + 12), (xc - 14, yc + 12), (xc - 14, yp + 24)], kind="acc")
    f.text(26, 296, "↑ 向上保留祖先目录", anchor="start", fs=11, cls="acc")
    f.text(236, 34 + 6 * 30 + 17, "空目录：没有被任何菜单保留", anchor="start", fs=11, cls="bad")

    f.arrow([(430, 140), (490, 140)], label="组树", fs=11)
    f.zone(500, 34, 260, 200, "侧边栏结果")
    side = [(0, "系统管理"), (1, "用户管理"), (0, "工单管理"), (1, "工单列表")]
    for i, (lvl, n) in enumerate(side):
        f.box(520 + lvl * 24, 60 + i * 38, 190 - lvl * 24, 28, [(n, {"fs": 12})],
              anchor="start", pad=10, rx=4, kind="" if lvl else "acc")
    return f.svg(), "catalog 没有权限码，自顶向下根本无法判断它该不该显示；自底向上时，目录的可见性就等于「是否有任一后代菜单被保留」。"


def fig_request_flow(ctx):
    f = Fig(780, 470, "一次受保护的列表请求：先过功能权限这道布尔关口，再在查询里套上数据权限的集合过滤，最后模板渲染时复用 L1 缓存")
    X, Wd = 200, 330
    steps = [
        (["浏览器 GET /tickets/"], ""),
        (["AuthenticationMiddleware", ("session → request.user", {"fs": 11, "mono": True, "cls": "mut"})], ""),
        (["@require_perm(TicketPerm.VIEW)", ("user_has_perm：超管短路 · L1 → L2 → DB", {"fs": 11, "cls": "mut"})], "acc"),
        (["TicketListView.get_queryset()", ("Ticket.objects.for_user(request.user)", {"fs": 11, "mono": True})], "acc"),
        (["模板渲染", ("{% if 'ticket:ticket:delete' in perms %}", {"fs": 11, "mono": True, "cls": "mut"})], ""),
        (["HTML 响应"], ""),
    ]
    bs = []
    for i, (rows, kind) in enumerate(steps):
        bs.append(f.box(X, 16 + i * 76, Wd, 50, rows, kind=kind, fs=13))
    for i in range(len(bs) - 1):
        f.arrow([bs[i].bottom(), bs[i + 1].top()])
    f.text(X - 16, bs[2].cy - 4, "功能权限", anchor="end", bold=True, cls="acc")
    f.text(X - 16, bs[2].cy + 14, "结果是布尔值", anchor="end", fs=11, cls="mut")
    f.text(X - 16, bs[3].cy - 4, "数据权限", anchor="end", bold=True, cls="acc")
    f.text(X - 16, bs[3].cy + 14, "结果是 WHERE 条件", anchor="end", fs=11, cls="mut")
    rj = f.box(580, bs[2].y, 180, 50, ["403.html", ("审计 perm.denied", {"fs": 11})], kind="bad")
    f.arrow([bs[2].right(), rj.left()], kind="bad", label="不通过", fs=11)
    sq = f.box(580, bs[3].y, 180, 50, [("build_scope_q → Q", {"fs": 11, "mono": True}),
                                        ("各角色 OR，SQL 层过滤", {"fs": 11})], kind="good")
    f.arrow([bs[3].right(), sq.left()], kind="good", fs=11)
    f.box(580, bs[4].y, 180, 50, ["命中 L1", ("零额外查询", {"fs": 11})], kind="good")
    f.arrow([bs[4].right(), (580, bs[4].cy)], kind="good")
    return f.svg(), "两道关口在不同层、用不同机制：功能权限在视图入口做布尔判断，数据权限在 ORM 层变成 SQL 条件。二者分开实现。"


def fig_bump_flow(ctx):
    f = Fig(800, 230, "权限变更的失效传播：写库触发 signal 或 RbacQuerySet，bump_version 让所有旧版本 key 不可达，下次请求按新版本重算")
    steps = [("管理员保存", "角色权限"), ("RolePermission", "写入"), ("signal /", "RbacQuerySet"),
             ("bump_version()", "7 → 8")]
    bs = []
    for i, (a, b) in enumerate(steps):
        bs.append(f.box(20 + i * 190, 24, 150, 50, [a, (b, {"fs": 11, "cls": "mut"})],
                        kind="acc" if i == 3 else "", fs=12))
    for i in range(len(bs) - 1):
        f.arrow([bs[i].right(), bs[i + 1].left()])
    f.text(bs[2].cx, 94, "post_save / post_delete / m2m_changed", fs=10, mono=True, cls="mut")
    f.text(bs[2].cx, 108, "queryset.update() 不发信号 → 在 QuerySet 层拦", fs=10, cls="mut")
    old = f.box(120, 150, 240, 50, [("rbac:perms:42:7", {"mono": True, "fs": 12}),
                                     ("立即不可达，等 TTL 淘汰", {"fs": 11})], kind="ghost", dashed=True)
    new = f.box(460, 150, 240, 50, [("rbac:perms:42:8", {"mono": True, "fs": 12}),
                                     ("用户 42 下一次请求时重算写入", {"fs": 11})], kind="good")
    f.arrow([bs[3].bottom(), (bs[3].cx, 124), (old.cx, 124), old.top()], kind="mut", dashed=True,
            seg=1, head=True)
    f.arrow([(bs[3].cx, 124), (new.cx, 124), new.top()], kind="good", head=True)
    return f.svg(), "满足 FR-4.5（最迟下一次请求生效）：管理员配完，用户刷新即见，无需重新登录。"


def fig_three_layers(ctx):
    f = Fig(780, 250, "功能权限的三层：菜单和按钮的隐藏只影响正常点击路径，直接构造请求会绕过它们，只有视图层在每条路径上")
    bands = [(180, "菜单层", "隐藏入口 · v0.11.0", ""), (320, "模板层", "隐藏按钮 · v0.10.0", ""),
             (460, "视图层", "@require_perm · v0.9.0", "acc")]
    for x, n, sub, kind in bands:
        f.rect(x, 50, 120, 170, cls="zone" + (" " + kind if kind else ""), rx=8)
        f.text(x + 60, 72, n, bold=True, cls=kind)
        f.text(x + 60, 90, sub, fs=10, cls="mut")
    f.path("M180 34 L440 34", cls="ln mut")
    f.text(310, 26, "体验优化", fs=12, cls="mut")
    f.path("M460 34 L580 34", cls="ln acc", width=2)
    f.text(520, 26, "安全边界", fs=12, cls="acc", bold=True)
    u = f.box(20, 110, 130, 40, "页面上点击")
    a = f.box(20, 170, 130, 40, [("curl -X POST", {"mono": True, "fs": 12})], kind="bad")
    f.arrow([u.right(), (640, u.cy)], label="", kind="")
    f.text(240, u.cy - 8, "看不见", fs=11, cls="mut", halo=True)
    f.text(380, u.cy - 8, "看不见", fs=11, cls="mut", halo=True)
    f.arrow([a.right(), (180, a.cy)], kind="bad", head=False)
    f.arrow([(180, a.cy), (460, a.cy)], kind="bad", dashed=True, head=False)
    f.text(320, a.cy - 8, "根本不经过", fs=11, cls="bad", halo=True)
    f.arrow([(460, a.cy), (640, a.cy)], kind="bad")
    f.circle(520, u.cy, 5, kind="acc")
    f.circle(520, a.cy, 5, kind="acc")
    f.box(640, 110, 124, 100, ["403 / 404", ("两条路都在", {"fs": 11}), ("这里被拦住", {"fs": 11})],
          kind="good")
    return f.svg(), "攻击者不需要点你的按钮，他直接 POST。每一个隐藏的按钮都必须在视图层有一个对应的 @require_perm。"


def fig_wrapper_chain(ctx):
    f = Fig(800, 250, "启动自检沿包装链找到真正的视图：函数视图读 _required_perm，类视图经 view_class 读 required_perm，都没有就报 rbac.W001")
    W_, G = 116, 40

    def chain(y, items):
        bs = []
        for i, (rows, kind) in enumerate(items):
            bs.append(f.box(20 + i * (W_ + G), y, W_, 48, rows, kind=kind, fs=12))
        return bs

    r1 = chain(20, [(["URLPattern", ("callback", {"fs": 11, "mono": True})], ""),
                    (["csrf_exempt", ("包装函数", {"fs": 11, "cls": "mut"})], ""),
                    (["login_required", ("包装函数", {"fs": 11, "cls": "mut"})], ""),
                    (["as_view()", ("闭包", {"fs": 11, "cls": "mut"})], ""),
                    (["TicketListView", ("required_perm ✓", {"fs": 11, "mono": True})], "good")])
    labels = ["", "__wrapped__", "__wrapped__", ".view_class"]
    for i in range(4):
        f.arrow([r1[i].right(), r1[i + 1].left()])
        if labels[i]:
            gx = (r1[i].r + r1[i + 1].l) / 2
            f.text(gx, r1[i].b + 14, labels[i], fs=10, mono=True, cls="mut")
    r2 = chain(100, [(["URLPattern", ("callback", {"fs": 11, "mono": True})], ""),
                     (["require_perm", ("_required_perm ✓", {"fs": 11, "mono": True})], "good")])
    f.arrow([r2[0].right(), r2[1].left()])
    r3 = chain(180, [(["URLPattern", ("callback", {"fs": 11, "mono": True})], ""),
                     (["some_view", ("无任何标记", {"fs": 11, "cls": "mut"})], "warn")])
    f.arrow([r3[0].right(), r3[1].left()])
    w = f.box(r3[1].r + G, 180, 250, 48, [("Warning  rbac.W001", {"mono": True, "fs": 12}),
                                          ("未声明权限要求，也没有 @public_view", {"fs": 11})], kind="bad")
    f.arrow([r3[1].right(), w.left()], kind="bad")
    f.text(r2[1].r + G, 130, "@public_view(reason=…) 同样算已声明：标记为 _is_public", anchor="start",
           fs=11, cls="mut")
    return f.svg(), "装饰器方案唯一的风险是「忘了加」，自检把它变成 runserver / check 时就能看到的告警。"


def fig_404(ctx):
    f = Fig(760, 210, "范围外返回 403 会让攻击者遍历 ID 画出记录分布；统一返回 404 时，范围外与不存在无法区分")
    ids = list(range(1, 11))
    exists = {1, 2, 4, 5, 7, 8, 10}
    mine = {1, 8}
    f.text(140, 26, "ticket id", anchor="end", fs=11, cls="mut")
    for i in ids:
        f.text(170 + (i - 1) * 52 + 22, 26, str(i), fs=12, mono=True)
    for row, (title, policy) in enumerate((("范围外 → 403", "403"), ("范围外 → 404", "404"))):
        y = 40 + row * 70
        f.text(140, y + 26, title, anchor="end", fs=12, bold=True)
        for i in ids:
            if i in mine:
                code, kind = "200", "good"
            elif i in exists:
                code, kind = (policy, "warn" if policy == "403" else "ghost")
            else:
                code, kind = "404", "ghost"
            f.box(170 + (i - 1) * 52, y, 44, 38, [(code, {"mono": True, "fs": 12})], kind=kind, rx=4)
    f.text(430, 190, "上一行：黄格暴露了哪 5 条记录「存在但不归你」；下一行：与不存在的 ID 无从区分", fs=12,
           cls="mut")
    return f.svg(), "功能权限不足（你根本没有 ticket:ticket:view）返回 403 没问题；数据范围之外的单条记录必须是 404。"


# ------------------------------------------------------------------ 04 横向对比

def fig_pushdown(ctx):
    f = Fig(800, 250, "逐行 enforce 要把全表拉进 Python；把规则翻译成 WHERE 后，数据库只返回范围内的行")
    f.text(20, 26, "路 A：全表扫描后逐行 enforce", anchor="start", bold=True, cls="bad")
    d1 = f.box(20, 40, 150, 50, ["数据库", ("80,000 张工单", {"fs": 11, "cls": "mut"})])
    p1 = f.box(330, 40, 230, 50, [("enforce(user, t, 'view')", {"mono": True, "fs": 12}),
                                  ("× 80,000 次", {"fs": 11, "cls": "bad"})], kind="bad")
    o1 = f.box(640, 40, 140, 50, ["页面 20 条"])
    f.arrow([d1.right(), p1.left()], kind="bad", width=9, label="SELECT * 全部行", fs=11)
    f.arrow([p1.right(), o1.left()])

    f.text(20, 146, "路 B：规则翻译成 WHERE（本项目）", anchor="start", bold=True, cls="good")
    q = f.box(20, 160, 200, 50, [("build_scope_q(user)", {"mono": True, "fs": 12}),
                                 ("→ Q 对象", {"fs": 11, "cls": "mut"})], kind="good")
    d2 = f.box(330, 160, 230, 50, ["数据库", ("WHERE department_id IN (…)", {"fs": 11, "mono": True})])
    o2 = f.box(640, 160, 140, 50, ["页面 20 条"])
    f.arrow([q.right(), d2.left()], kind="good", label="ORM 参数化", fs=11)
    f.arrow([d2.right(), o2.left()], kind="good", label="LIMIT 20", fs=11)
    return f.svg(), "箭头粗细代表搬运的数据量。Casbin 的 enforce() 回答「这一个请求能不能过」；列表页需要的是「能看的全部」，只有能翻译成 SQL 的规则才分得了页。"


def fig_ruoyi_vs_q(ctx):
    f = Fig(800, 300, "若依在切面里拼 SQL 字符串并通过 XML 占位符注入，调用点看不到过滤；本项目在调用点显式 for_user，内核返回 Q 对象")
    f.zone(10, 10, 380, 280, "若依：@DataScope + AOP + ${}")
    ra = f.box(30, 40, 340, 40, [("userService.selectUserList(user)", {"mono": True, "fs": 12})],
               kind="ghost")
    f.text(210, 99, "调用点：看不出会被过滤", anchor="start", fs=11, cls="bad")
    rb = f.box(30, 110, 340, 40, [("@DataScope 切面 → 拼接 SQL 字符串", {"fs": 12})], kind="warn")
    rc = f.box(30, 180, 340, 40, [("params.dataScope = \" OR u.dept_id IN (…)\"", {"mono": True, "fs": 11})],
               kind="warn")
    rd = f.box(30, 240, 340, 40, [("<select> … WHERE 1=1 ${params.dataScope}", {"mono": True, "fs": 11})])
    f.arrow([ra.bottom(), rb.top()], kind="mut", dashed=True)
    f.arrow([rb.bottom(), rc.top()])
    f.arrow([rc.bottom(), rd.top()])

    f.zone(410, 10, 380, 280, "本项目：显式 for_user + Q")
    qa = f.box(430, 40, 340, 40, [("Ticket.objects.for_user(request.user)", {"mono": True, "fs": 12})],
               kind="good")
    f.text(610, 99, "调用点：一眼可见，grep 可查", anchor="start", fs=11, cls="good")
    qb = f.box(430, 110, 340, 40, [("build_scope_q(user, ScopeConfig) 纯函数", {"fs": 12})], kind="acc")
    qc = f.box(430, 180, 340, 40, [("Q(creator_id=…) | Q(department_id__in=…)", {"mono": True, "fs": 11})],
               kind="acc")
    qd = f.box(430, 240, 340, 40, [("ORM 参数化 SQL · 可与其他 Q 组合", {"fs": 12})])
    f.arrow([qa.bottom(), qb.top()])
    f.arrow([qb.bottom(), qc.top()])
    f.arrow([qc.bottom(), qd.top()])
    return f.svg(), "两边的合并规则一致（OR 并集、ALL 短路、无匹配时拒绝），差别在机制：字符串拼接 vs 可组合、可单测的 Q 对象；以及过滤在调用点是否可见——左边是否生效，取决于方法上有没有 @DataScope 注解。"


def fig_decision_tree(ctx):
    f = Fig(800, 380, "选型决策树：先问是否需要集合查询，再问授权关系是人工指定还是规则推导")
    q1 = f.box(250, 16, 300, 46, "需要「列出我能看的所有数据」吗？", kind="warn")
    qa = f.box(30, 112, 250, 46, [("多语言微服务 / 策略形状常变？", {"fs": 12})])
    qb = f.box(420, 112, 340, 46, "授权关系是人工指定，还是规则推导？", kind="warn")
    f.arrow([(q1.cx - 60, q1.b), (q1.cx - 60, 88), (qa.cx, 88), qa.top()],
            label="不需要（只做单点鉴权）", seg=1, fs=11)
    f.arrow([(q1.cx + 60, q1.b), (q1.cx + 60, 88), (qb.cx, 88), qb.top()], label="需要", seg=1,
            fs=11)
    cas = f.box(20, 214, 110, 42, "Casbin")
    dj = f.box(160, 214, 130, 42, "Django 原生")
    f.arrow([(qa.cx - 50, qa.b), (qa.cx - 50, 186), (cas.cx, 186), cas.top()], label="是", seg=1,
            fs=11)
    f.arrow([(qa.cx + 50, qa.b), (qa.cx + 50, 186), (dj.cx, 186), dj.top()], label="否", seg=1,
            fs=11)
    gd = f.box(330, 214, 170, 52, ["django-guardian", ("量大时改直接外键模式", {"fs": 11, "cls": "mut"})])
    q3 = f.box(540, 214, 240, 52, [("需要角色继承 / 溯源 /", {"fs": 12}), ("树形权限点？", {"fs": 12})],
               kind="warn")
    f.arrow([(qb.cx - 80, qb.b), (qb.cx - 80, 188), (gd.cx, 188), gd.top()],
            label="人工指定（alice 分享给 bob）", seg=1, fs=11, lpos=(gd.cx + 8, 182), lanchor="middle")
    f.arrow([(qb.cx + 80, qb.b), (qb.cx + 80, 188), (q3.cx, 188), q3.top()], label="", seg=1)
    f.text(q3.cx + 40, 182, "规则推导", fs=11, halo=True)
    own = f.box(480, 320, 150, 44, "自建（本项目）", kind="acc")
    ry = f.box(650, 320, 140, 44, ["若依", ("Java 生态 + 要快", {"fs": 11, "cls": "mut"})])
    f.arrow([(q3.cx - 50, q3.b), (q3.cx - 50, 294), (own.cx, 294), own.top()], label="需要", seg=1,
            fs=11)
    f.arrow([(q3.cx + 50, q3.b), (q3.cx + 50, 294), (ry.cx, 294), ry.top()], label="不需要", seg=1,
            fs=11)
    return f.svg(), "三条路线不互斥。常见组合是 RBAC 打底 + 数据范围做列表过滤 + 少量对象级授权做分享，本项目的 ScopeConfig.extra_q 就是给第三种留的缝。"


# ------------------------------------------------------------------ HTML 表格

MATRIX_ROWS = [
    ("用户列表", ["✅", "✅", "❌", "❌", "❌", "↪登录"]),
    ("角色配置", ["✅", "✅", "❌", "❌", "❌", "↪登录"]),
    ("工单列表", ["全部", "全部", "本部门树", "仅本人", "空", "↪登录"]),
    ("工单删除", ["✅", "❌", "✅", "❌", "❌", "↪登录"]),
    ("他部门单", ["✅", "可见", "404", "404", "404", "↪登录"]),
]
MATRIX_COLS = ["超管", "系统管理员", "客服主管", "客服专员", "无角色用户", "匿名"]


def html_matrix(ctx):
    def cls(v):
        return {"✅": "ok", "可见": "ok", "全部": "ok", "❌": "no", "404": "no", "空": "no",
                "↪登录": "redir"}.get(v, "part")

    head = "".join(f"<th>{c}</th>" for c in MATRIX_COLS)
    body = "".join(
        "<tr><th>" + r + "</th>" + "".join(f'<td class="{cls(v)}">{v}</td>' for v in vals) + "</tr>"
        for r, vals in MATRIX_ROWS
    )
    table = (f'<div class="table-wrap"><table class="matrix"><thead><tr><th></th>{head}</tr>'
             f"</thead><tbody>{body}</tbody></table></div>")
    return table, "每个格子对应一个参数化测试用例。任何一格从 ❌ 变 ✅ 都是安全事故，CI 会立刻变红。"


FIGS = {name[4:]: fn for name, fn in list(globals().items())
        if name.startswith("fig_") and callable(fn)}
FIGS["matrix"] = html_matrix
