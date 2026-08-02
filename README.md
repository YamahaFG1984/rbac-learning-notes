# RBAC 教学项目：用 Django 5.2 从零实现一套企业级权限系统

这是一个**教学导向**的工程项目。目标不是交付一个可以直接商用的权限中台，而是把「一套 RBAC 系统是怎么一步步长出来的」完整地、可复现地记录下来——包括每一处设计取舍的**理由**和**代价**。

## 它和网上那些「RBAC 示例代码」有什么不同

大多数示例代码只给你最终形态：一堆模型、一堆装饰器，跑起来能用，但你不知道为什么是这样。这个项目的组织方式是：

1. **先有文档，再有代码。** PRD 说清楚要做什么，设计文档说清楚为什么这么做，实施计划说清楚按什么顺序做。
2. **每个功能一个 Git tag。** 你可以 `git diff v0.4.0 v0.5.0` 看清楚「加入用户-角色绑定」到底改动了哪些文件、为什么。
3. **每个 tag 都能跑起来。** 不存在「中间态是坏的，最后一次性调通」。
4. **取舍写在明处。** 设计文档里有 16 条 ADR（架构决策记录），每条都写了备选方案、为什么选它、以及这个选择的代价。

## 项目规格

| 项 | 值 |
| --- | --- |
| Django | 5.2.16（LTS） |
| Python | 3.12 |
| RBAC 层级 | NIST RBAC1（核心 RBAC + 角色继承）+ 数据行级权限 |
| 交付形态 | 阶段一：Django 模板 + Tailwind CSS（前后端不分离）<br>阶段二：DRF + JWT（前后端分离），复用同一权限内核<br>阶段三：React SPA（`feat/react-frontend` 分支），同一内核的第三种表现层 |
| 多租户 | 不支持（单组织，部门树用于数据权限范围，不做租户隔离） |
| 数据库 | SQLite（开发/教学）→ PostgreSQL（可选切换） |

## 文档

| 文档 | 内容 |
| --- | --- |
| [`docs/00-RBAC理论基础.md`](docs/00-RBAC理论基础.md) | **前置阅读**：访问控制模型演进、NIST RBAC 标准、数据权限的理论定位 |
| [`docs/01-PRD.md`](docs/01-PRD.md) | 产品需求文档：做什么、给谁用、验收标准 |
| [`docs/02-设计文档.md`](docs/02-设计文档.md) | 技术设计：架构、数据模型、核心算法、16 条 ADR |
| [`docs/03-实施计划.md`](docs/03-实施计划.md) | 总纲与索引：tag 规范、环境准备、贯穿全项目的几条原则、学习自检清单 |
| [`docs/tags/`](docs/tags/) | **22 份可独立实现的 tag 规格书**，每份含思考题、接口契约、陷阱预警、渐进提示、自测清单、对比检查点 |
| [`docs/04-横向对比.md`](docs/04-横向对比.md) | 与 Django 原生 / django-guardian / Casbin / 若依 的对照分析、选型决策树 |
| [`CLAUDE.md`](CLAUDE.md) | 工程约定：命名规范、依赖方向、安全红线、每个 tag 的完成定义 |
| [`docs/frontend/`](docs/frontend/) | **阶段三（`feat/react-frontend` 分支）**：React 前端的 PRD、15 条 F-ADR、17 份 tag 规格书 |
| [`frontend/CLAUDE.md`](frontend/CLAUDE.md) | 前端工程约定（`feat/react-frontend` 分支） |

> `04-横向对比.md` 建议在完成到 `v0.14.0`（数据权限）之后再读——
> 没亲手实现过就去读别人的方案，只能记住结论，记不住原因。

## 怎么用这个项目学习

### 方式 A：自己实现，再对比（推荐，约 55~75 小时）

每份 tag 规格书都是**可以照着独立实现**的——有接口契约、实现步骤、陷阱预警，但不直接给答案。

```bash
# 0. 读 docs/00-RBAC理论基础.md + 另外三份文档（约 2.5 小时）
# 1. 打开对应 tag 的规格书，先做「一、动手之前先想清楚」的思考题
#    docs/tags/01-v0.1.0-项目骨架.md
# 2. 照着「接口契约」和「实现步骤」自己写
#    卡住了才展开「六、卡住了看这里」的折叠提示
# 3. 跑「七、自测清单」
# 4. 对照我的实现，逐条走「八、和我的实现对比什么」
git diff v0.1.0 v0.2.0 -- ':!static/css/tailwind.css'
```

> ⚠️ **「接口契约」那一节请照抄。** 字段名、函数签名不一致的话，diff 会全是噪音，看不出真正的设计差异。契约照抄，实现自由发挥——这正是真实协作中「接口先行」的意义。

### 方式 B：只读代码和 diff（约 10 小时）

```bash
git checkout v0.5.0
git diff v0.5.0 v0.6.0 -- ':!static/css/tailwind.css'
```

然后读该 tag 规格书的「五、陷阱」「八、对比点」「九、延伸思考」三节。

**不管哪种方式，都不要一次看完。** 每个 tag 停下来问自己「如果是我，这一步会怎么设计」。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # 生成演示数据
python manage.py runserver
```

打开 http://127.0.0.1:8000/accounts/login/ ，统一密码 `demo1234`：

| 账号 | 说明 | 侧边栏 | 可见工单 | 能删工单 | 访问技术部工单 |
| --- | --- | --- | --- | --- | --- |
| `superadmin` | 超管，绕过一切 | 全部 | 80 | ✅ | 可见 |
| `sysadmin` | 系统管理员，`data_scope=ALL` | 系统管理 | 80 | ❌ | 可见 |
| `cs_manager` | 客服主管，继承客服专员，本部门及以下 | 工单管理 | 50 | ✅ | **404** |
| `cs_staff` | 客服专员，仅本人 | 工单管理 | 5 | ❌ | **404** |
| `no_role` | 无角色 | **空** | **0** | ❌ | 404 |

> 用 `cs_staff` 登录后，把工单详情 URL 里的 ID 换成技术部工单的 ID——
> 会得到 **404 而不是 403**。这不是找不到，是「对你而言它不存在」
> （见 [ADR-009](docs/02-设计文档.md)）。

### 常用命令

```bash
pytest                                              # 417 个测试，约 18 秒
pytest tests/security/ -v                           # 只跑越权测试
pytest --cov --cov-report=term                      # 覆盖率
python manage.py check                              # 含 rbac.W001/W002 权限声明自检
python manage.py sync_permissions --check-templates  # 检查模板里的权限码 typo
bash scripts/smoke_all_tags.sh                      # 遍历所有 tag 冒烟测试
```

## 阶段三：React SPA（`feat/react-frontend` 分支）

同一个权限内核的第三种表现层。**内核一行都没有改**——
这是这个阶段最重要的验收条件，也是 ADR-013 那条「内核不认识表现层」
约束的真正兑现时刻：

```bash
git checkout feat/react-frontend
git diff main HEAD -- apps/rbac/services.py     # 期望输出为空
```

```bash
# 后端照常起
python manage.py runserver

# 另开一个终端
cd frontend && npm install && npm run dev       # http://localhost:5173
```

> ⚠️ 只访问 **:5173**，不要直接开 :8000 的 SPA 页面。
> 同域是 httpOnly Cookie 方案的硬性前提（F-ADR-002），
> Vite 的代理把 `/api` 转给 Django，全程单一源、不需要 CORS。

### 这个阶段真正要回答的问题

Django 模板版里，界面和权限判断是**同一次请求**产生的；
SPA 手里是一份**快照**。由此产生一整类模板版根本不存在的问题：

| 问题 | 在哪解决 |
| --- | --- |
| 撤权之后，用户屏幕上的按钮还在 | `fe-v0.13.0` 版本号感知 |
| 403 被当成 401 处理 → 登录死循环 | `fe-v0.14.0` 错误分流 |
| 刷新详情页变 404（路由表还没建好） | `fe-v0.7.0` 时序 |
| 前端藏了按钮、后端忘了拦 | `fe-v0.15.0` 结构性对账 |

### 🎯 最值得看的一个文件

```bash
cat frontend/e2e/bypass.spec.ts
```

它用四步证明**前端权限的安全价值是零**：

```
隐藏了 → 可以改回来 → 改回来也没用 → 连前端都不用
```

> 前端权限是给用户的，后端权限是给攻击者的。

### 前端常用命令

```bash
cd frontend
npm run test           # 98 个单测
npm run test:coverage  # 权限相关模块 ≥ 90%
bash ../scripts/e2e.sh # 92 条 E2E（含越权矩阵），自动重置数据 + 起服务
```
