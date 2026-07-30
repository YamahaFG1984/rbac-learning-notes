# CLAUDE.md — 项目工程约定

本文件是本仓库的**工程契约**，对人和对 AI 助手同等生效。

---

## 0. 首要原则：这是教学项目，跨 tag 的 diff 是核心产物

本项目的价值不在最终代码，而在 **23 个 tag 之间的差异**。学习者通过 `git diff v0.13.0 v0.14.0` 理解「数据权限是怎么加进去的」。

由此推出三条不可协商的约束：

| # | 约束 | 原因 |
| --- | --- | --- |
| 1 | **风格一致性优先于局部最优** | 第 5 个 tag 和第 20 个 tag 的代码风格必须看起来是同一个人写的。风格漂移会直接污染 diff 的信噪比 |
| 2 | **严禁提前实现后续 tag 的功能** | 见下，这是最容易违反的一条 |
| 3 | **严禁在后续 tag 里大规模重构前面的代码** | 无关的格式化、改名、挪文件会把一个 50 行的功能 diff 撑成 500 行 |

### 关于「严禁提前实现」

实施计划里每个 tag 的范围是**刻意划定**的。即使你在写 `v0.6.0` 的权限解析时，一眼就看到这里该加缓存——**也不要加**。缓存属于 `v0.16.0`。

三个刻意留下的不安全中间态（`v0.8.0` 写死菜单、`v0.13.0` 无数据权限、`v1.1.0` 无授权）同理，它们不是疏漏，是教学设计。见实施计划第 7 章。

如果你认为某个 tag 的范围划分有问题，**提出来讨论并修改实施计划文档**，不要在代码里单方面越界。

---

## 1. 文档与权威顺序

| 文档 | 内容 |
| --- | --- |
| `docs/00-RBAC理论基础.md` | 前置阅读：访问控制模型演进、NIST RBAC 标准、数据权限的理论定位 |
| `docs/01-PRD.md` | 需求（FR-x / NFR-x / AC-x 编号在此定义） |
| `docs/02-设计文档.md` | 16 条 ADR、数据模型、核心算法、安全设计 |
| `docs/03-实施计划.md` | 23 个 tag 的范围、验收标准、学习要点 |

**冲突时的权威顺序**：`PRD` > `设计文档` > `实施计划` > `代码`。

代码与文档不一致时，**先改文档再改代码**，不要让代码悄悄漂离文档——文档是这个项目的主要交付物。

---

## 2. 环境与常用命令

```bash
source .venv/bin/activate

python manage.py check                  # 含 rbac.W001 权限声明自检（v0.9.0 起）
python manage.py migrate
python manage.py runserver

python manage.py sync_permissions       # 同步代码声明的权限点（v0.4.0 起）
python manage.py seed_demo              # 生成演示数据（v1.0.0 起）
python manage.py rebuild_dept_path      # 重建部门 path 冗余字段（v0.3.0 起）

pytest
pytest --cov=apps --cov-report=term-missing

npm run build:css                       # 提交前必跑（产物入库，见 ADR-015）
npm run watch:css                       # 开发时
```

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12.3 | |
| Django | **5.2.16** | LTS，锁死小版本 |
| 数据库 | SQLite | `DATABASE_URL` 可切 PostgreSQL；**禁止使用任何数据库特有字段**（ADR-014） |
| Node | 24.x | 仅 Tailwind CLI |

---

## 3. 目录与依赖方向

```
config/                  项目配置
apps/
  common/                共享基类、工具
  accounts/              组织域：User、Department
  rbac/                  授权域：Permission、Role、UserRole、RolePermission、权限内核
  tickets/               业务示例
  audit/                 审计日志
```

**依赖方向严格单向**（PRD `NFR-8`）：

```
tickets ──┐
          ├──> rbac ──> accounts ──> common
audit   ──┘
```

**禁止反向 import。** `apps/accounts` 里出现 `from apps.rbac import ...` 是必须拒绝的变更。

### 两条额外的硬约束

**A. `apps/rbac/services.py` 不得 import 任何 `django.http` / DRF 的东西**（ADR-013）

这是权限内核的纯净性约束。它的收益在 `v1.2.0` 一次性兑现——届时的验收条件是：

```bash
git diff v1.1.0 v1.2.0 -- apps/rbac/services.py   # 期望输出为空
```

**B. 所有需要部门子树的地方，必须走 `services.get_user_dept_ids()`**（ADR-016）

不要在业务代码里散落 `Department.objects.filter(path__startswith=...)`。收敛到一个函数，将来解耦时改动面才可控。

---

## 4. 命名规范

### 权限码（ADR-004）

格式 `{app}:{resource}:{action}`，全小写，词内下划线。

```
system:user:view          ticket:ticket:export       system:role:assign_perm
```

- `action` 取自受控词表：`view` / `create` / `update` / `delete` / `export` / `import` / `assign` / `assign_perm` / `audit`。需要新动词时，先在设计文档 ADR-004 的表里加，再用。
- `catalog` 类型的权限点**无权限码**（`code=None`），它只是分组容器。
- **权限码必须在 `apps/<app>/permissions.py` 中声明**，通过 `sync_permissions` 入库。禁止手工往数据库塞权限点。
- **视图和模板里禁止写裸字符串**，一律用常量类：

```python
class TicketPerm:
    VIEW   = "ticket:ticket:view"
    CREATE = "ticket:ticket:create"
```

### 其他

| 对象 | 规范 | 示例 |
| --- | --- | --- |
| URL name | `<app>:<action>` | `tickets:list`、`tickets:detail` |
| 模板路径 | `<app>/<name>.html` | `tickets/list.html` |
| 模板片段 | 下划线前缀 | `tickets/_row.html` |
| 测试文件 | `tests/<app>/test_<模块>.py` | `tests/rbac/test_services.py` |
| 模型 verbose_name | **必填中文** | `models.CharField("姓名", ...)` |
| 迁移文件 | 必须有描述性名字 | `makemigrations -n add_role_inherits_from` |

---

## 5. 编码约定

### 模型

字段按固定顺序排列，跨 tag 保持一致：

```python
class Role(TimestampedModel):
    # 1. 业务标识
    code = models.CharField("角色编码", max_length=64, unique=True)
    name = models.CharField("角色名称", max_length=64)
    # 2. 关系
    inherits_from = models.ForeignKey("self", ...)
    # 3. 业务属性
    data_scope = models.SmallIntegerField(...)
    # 4. 排序与状态
    order_num = models.SmallIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    # 5. 时间戳来自 TimestampedModel
```

| 约定 | 规则 |
| --- | --- |
| `on_delete` | 树形父节点和被引用的主数据一律 `PROTECT`。**用数据库约束表达业务规则，比在 `delete()` 里写检查更难被绕过** |
| 默认值方向 | **默认值必须指向「出错时后果最轻」的方向**。`data_scope` 默认 `SELF_ONLY`（最窄）不是 `ALL`；`is_active` 视语义定 |
| 冗余字段 | `path` / `depth` 标 `editable=False`，只在 `save()` 里维护，禁止手工赋值 |
| ForeignKey | 必须显式写 `related_name` |

### 查询

| 约定 | 规则 |
| --- | --- |
| 数据权限 | **必须显式 `.for_user(user)`**（ADR-009）。禁止任何形式的隐式/thread-local 自动过滤 |
| 单条获取 | `get_object_or_404(Model.objects.for_user(user), pk=pk)`。禁止「先取出再判断」——那是 IDOR 漏洞的标准写法 |
| 范围外 | 一律 **404**，不是 403。403 会泄露记录存在性 |
| N+1 | 列表查询必须 `select_related` / `prefetch_related`，并用 `assertNumQueries` 锁死 |

### ⚠️ `Q()` vs `Q(pk__in=[])`

```python
Q()             # 空条件 → 不过滤 → 返回全集
Q(pk__in=[])    # 不可满足条件 → 返回空集
```

差两个字符，安全后果天差地别。`build_scope_q()` 里有**四处默认拒绝分支**必须返回 `Q(pk__in=[])`（设计文档 4.3）：未登录/已禁用、无任何角色、scope 不可识别、用户无部门。

**这四处每一处都必须有对应测试用例**——它们在正常使用中永不触发，只有测试能保证它们是对的。

---

## 6. 安全红线（不可协商）

| # | 红线 |
| --- | --- |
| 1 | **默认拒绝**。没有显式授权 = 拒绝。没有权限装饰器的视图 = 配置错误（`rbac.W001` 告警），不是公开访问 |
| 2 | **模板隐藏按钮不是安全边界**。每一个受控按钮，必须有对应的服务端 `@require_perm`。成对出现，缺一不可 |
| 3 | **表单用白名单 `fields`，禁止用 `exclude`**。黑名单会让将来新增的敏感字段自动进入表单——这是随时间自然劣化的设计 |
| 4 | **`is_superuser` 永不出现在任何 Web 表单里**。超管只能通过 `createsuperuser` 创建。否则任何有 `system:user:update` 权限的人都能自我提权 |
| 5 | **权限规则只能有一处实现**。禁止在视图里重复写数据范围判断——它和 `build_scope_q` 的规则迟早不一致，而不一致的那一刻就是漏洞诞生的时刻 |
| 6 | **权限变更必须 `bump_version()`**（`v0.16.0` 起）。通过 signal 挂载，不靠在视图里手写调用 |
| 7 | **审计日志只写不改不删** |

---

## 7. 测试要求

| 类型 | 要求 |
| --- | --- |
| 覆盖率 | `apps/rbac` ≥ 90%，整体 ≥ 85% |
| 默认拒绝 | 四处分支各一个用例 |
| 数据范围 | 五个枚举值各至少一个用例 |
| 越权矩阵 | 设计文档 6.2 的表格全格覆盖（`v0.19.0`） |
| 查询次数 | 关键路径用 `assertNumQueries` 锁死。权限代码极易引入 N+1 |

**两条特别说明**

- `assertNumQueries` 在权限系统里是**必备**而非可选。菜单树、每个按钮的权限判断都是 N+1 的高发区，把数字写死是唯一能防回退的手段。
- 越权矩阵不只是测试，它是**可执行的权限规格说明书**。文档会过期，测试不会——过期的测试会变红。

---

## 8. 每个 Tag 的完成定义（DoD）

打 tag 前逐条确认：

- [ ] 实施计划中该 tag 的「交付」条目全部完成
- [ ] 「验收」条目全部通过
- [ ] `python manage.py check` 无 error、无 `rbac.W001`
- [ ] `migrate` + `runserver` 正常，声明的功能可用
- [ ] `pytest` 全绿，本 tag 新增逻辑有测试
- [ ] `npm run build:css` 已跑
- [ ] 代码变更 ≤ 400 行（不含迁移文件和 CSS 产物），超出则拆 tag
- [ ] **没有提前实现后续 tag 的内容**
- [ ] **没有对既有代码做与本 tag 无关的重构**
- [ ] 文档中若有与本 tag 实现不符之处，已同步更新文档

### 提交与打 tag

```bash
npm run build:css && pytest
git add -A
git commit -m "feat(v0.6.0): 用户-角色绑定与有效权限解析"
git tag -a v0.6.0 -m "实现 UserRole 模型与 get_user_perm_codes()。对应 FR-4.1/4.3。"
```

- 提交信息格式：`<type>(<tag>): <中文描述>`，type 取 `feat` / `fix` / `docs` / `test` / `refactor`
- tag 注释必须写明：做了什么 + 对应哪些需求编号
- **一个 tag 一个 commit**。不要在 tag 之间留下游离提交，那会让 `git diff <tag1> <tag2>` 和 `git log` 讲的故事不一致

### 对比 diff 时排除 CSS 产物

```bash
git diff v0.7.0 v0.8.0 -- ':!static/css/tailwind.css'
```

---

## 9. 语言约定

| 场景 | 语言 |
| --- | --- |
| 文档、注释、`verbose_name`、界面文案、提交信息 | 中文 |
| 代码标识符、权限码、URL name、模板文件名 | 英文 |
| 注释密度 | **只解释「为什么」，不解释「是什么」**。涉及安全取舍的地方必须写明理由并引用对应 ADR 编号 |
