# frontend/CLAUDE.md — React 前端的工程约定

本文件是 `frontend/` 目录的工程契约，对人和 AI 助手同等生效。
仓库根目录的 `CLAUDE.md` 仍然适用，本文件只补充前端特有的部分。

---

## 0. 首要原则：前端权限是体验，不是安全

这一条统领本文件其余所有内容。

> **前端权限是给用户的，后端权限是给攻击者的。**

路由守卫、动态菜单、`<Can>` 按钮——这三层加起来的安全价值是**零**。
它们让用户不去点一个必然失败的东西，仅此而已。
`e2e/bypass.spec.ts` 用四步证明了这件事：

```
隐藏了 → 可以改回来 → 改回来也没用 → 连前端都不用
```

由此推出两条硬约束：

| # | 约束 |
| --- | --- |
| 1 | **每一个 `<Can perm={X}>` 都必须有一个对应的服务端校验。** 由 `tests/structural/permCoverage.test.ts` 自动对账，不靠人看 |
| 2 | **前端绝不重新实现任何权限规则。** 判断结果由后端下发，前端只渲染 |

⚠️ **路由守卫比隐藏按钮更容易造成错觉**，因为它写起来太像鉴权了。
`PermissionGate.tsx` 顶部那段注释不是废话，改动那个文件时请重读一遍。

---

## 1. 技术栈与版本

| 组件 | 选择 | 理由 |
| --- | --- | --- |
| 构建 | Vite | |
| 语言 | TypeScript **strict** | 权限码的类型收窄是 SPA 唯一比模板版更强的地方 |
| 路由 | React Router | |
| 服务端状态 | TanStack Query v5 | ⚠️ v5 **移除了 `useQuery` 的 `onSuccess`**，且是静默失效 |
| 客户端状态 | Zustand | |
| UI | Ant Design 6 | ⚠️ 部分 API 与 5 不同，见第 6 节 |
| 单测 | Vitest + Testing Library + MSW | |
| E2E | Playwright | |

---

## 2. 状态归属：三条线不能混

| 数据 | 归属 | 放哪 |
| --- | --- | --- |
| 列表、详情、任何来自服务端的东西 | 服务端状态 | **TanStack Query** |
| 当前用户、权限码、菜单 | 服务端状态的快照 | **Zustand（`authStore`）** |
| 分页、筛选条件 | 客户端状态，但属于**地址** | **URL search params** |
| 侧边栏折叠等纯 UI | 客户端状态 | Zustand（`uiStore`） |

⚠️ 分页/筛选放 `useState` 是最常见的错误：刷新后条件丢失、链接无法分享。

### `authStore` 的唯一写入口

```ts
// ✅ 只有 useProfileQuery 能写
useAuthStore.setProfile(profile)
```

**除 `useProfileQuery` 外，任何地方都不许调 `setProfile`。**
两处写入 = 两个真相源，很快就会不一致。

### 三态而非布尔

```ts
status: 'unknown' | 'authenticated' | 'anonymous'
```

⚠️ **「还没问过后端」≠「确定未登录」。** 用布尔值的话初始 `false`
会被当成「未登录」，应用启动瞬间闪一下登录页。
更危险的是有人写出 `perms.length === 0 ? 显示全部 : 按权限显示`
（理由是「还没加载完就先都显示吧」）——那会真的闪现越权内容。

---

## 3. 目录与依赖方向

```
src/
  api/          请求层：client / 各资源的请求函数 / 错误分流 / 版本号感知
  auth/         认证与权限：store、profile 查询、usePermission
  components/   通用组件：Can、错误边界、结果页
  features/     业务功能模块（按领域分）
  hooks/        通用 hook
  layouts/      布局与菜单
  pages/        路由页面（⚠️ 文件名与后端 component 字段对应）
  router/       动态路由注册与守卫
  constants/    ⚙️ 由后端生成，禁止手工编辑
  test/         测试夹具与 MSW（不进生产包）
```

**禁止的依赖方向**：

- `api/` 不得 import 路由、UI 组件或 Query 客户端
  → 需要它们的能力时，由 `App.tsx` 用 `setXxxHandler` / `configureXxx` **注入**
- `components/` 不得 import `pages/`
- `auth/` 不得 import `features/`

---

## 4. 权限相关的硬规则

### 权限码

```tsx
// ✅ 常量 + PermCode 类型，写错编译期报错
<Can perm={PERM.TICKET_TICKET_DELETE}>

// ❌ 裸字符串，写错静默不渲染（和模板版一样糟）
<Can perm="ticket:ticket:delet">
```

`src/constants/permissions.ts` 由 `python manage.py export_perm_constants` 生成。
后端权限点变更后必须重新生成并提交，CI 会用 `--check` 校验。

### 两种接口，一个判断函数

```tsx
<Can perm={...}>          // 组件式：控制**渲染**
const can = usePermission()  // hook 式：控制**数据**（Table columns、Menu items）
```

两者内部**必须**调用同一个 `usePermission()`。
写两遍的话，将来加语法要改两处，而且很可能只改一处。

### `<Can>` 不传 `perm` 时**不渲染**

「默认拒绝」在前端的形态。写漏了立刻可见，而不是静默放行。

### 绝不做数据的二次过滤

```tsx
// ❌ 看起来像多一道保险，实际是制造不一致的源头
const visible = data.results.filter((t) => canSee(t))
```

分页错乱、统计对不上，而且**零安全价值**（数据早就到浏览器了）。
`tests/unit/no-client-side-filtering.test.ts` 扫源码守这条。

---

## 5. 错误处理

| 状态码 | 动作 |
| --- | --- |
| **401** | 跳登录（带 redirect），**不弹提示**，并发去重 |
| **403** | 提示 + 重拉 profile，**绝不跳登录页** |
| **404 / 400** | 拦截器**不处理**，交给调用方 |
| **429** | 显示后端的 `detail` |
| **5xx** | 错误边界整页替换，**不弹 toast** |
| 无 response | 「网络连接失败」，不是「服务器错误」 |

🔴 `if (status === 401 || status === 403) redirectToLogin()` 是本项目最不能写的一行。
它造成「登录 → 403 → 登录」的死循环，用户会以为账号坏了。

⚠️ 拦截器处理完**必须继续 `reject`**。吞掉的话调用方拿到「成功但 data 是 undefined」。

⚠️ 一律优先用后端的 `detail`，不硬编码文案——否则两边会漂移。

---

## 6. Ant Design 6 的几个坑

```tsx
// ⚠️ autoInsertSpace 默认为 true：「登录」渲染成「登 录」，
//    所有按文本查找按钮的代码（含测试）全部失效，而报错指不到原因。
//    在 AntD 6 里它位于 button 命名空间下，写成顶层属性是 TS 错误。
<ConfigProvider button={{ autoInsertSpace: false }}>
```

| 项 | 说明 |
| --- | --- |
| `Spin` 的 `tip` | 已废弃，用 `description` |
| `Modal` 的 `destroyOnClose` | 已废弃，用 `destroyOnHidden` |
| `Tree` 的父子联动 | 权限场景一律 `checkStrictly` —— 必须完全掌控「哪些 key 会被提交」 |
| `message` 的存活时间 | 默认 3 秒，写 E2E 时**先断言它再断言持久状态** |

---

## 7. 测试分层

| 层 | 用什么 | 测什么 |
| --- | --- | --- |
| `tests/unit/` | Vitest | 纯函数、单组件 |
| `tests/integration/` | + MSW | 拦截器、认证流程 |
| `tests/structural/` | 源码扫描 | 前后端一致性对账 |
| `e2e/` | Playwright | 越权矩阵、cookie、路由时序 |

### 三条不可协商的测试规则

1. **MSW 拦网络层，不 `vi.mock('axios')`。**
   我们有一半的权限逻辑在拦截器里，mock 掉 axios 它们一行都不会执行。

2. **断言「被拒绝」时，必须再证明「换个身份就不会被拒绝」。**
   一个 403 测试如果因为 CSRF 没带对而通过，它是**假绿**——
   比没有测试更糟，因为它给人安全感。
   （这条我在 `fe-v0.9.0` 写下、在 `fe-v0.16.0` 又犯了一次。）

3. **一条测试只测一件事**，否则你分不清它到底在测什么。

### 有些东西单测测不了，别硬测

`document.cookie` 的 httpOnly 语义、绕过前端直调 API、真实浏览器的
history 行为——jsdom 都做不到。硬测会写出「测了但没测到」的假测试。

### E2E 的数据基线

E2E 跑在**共享的、可变的**数据库上。会改数据的 spec 必须
`beforeAll` / `beforeEach` 调 `reseedDatabase()`。

⚠️ **不要**为了让测试变绿而把绝对断言（`共 50 条`）改成相对的——
那个数字必须等于后端的 `SCOPE_MATRIX`，正是那条用例存在的理由。

---

## 8. 常用命令

```bash
npm run dev            # 开发（Vite dev server + 同域代理）
npm run build          # 生产构建
npm run typecheck
npm run test           # 单测
npm run test:coverage  # 带覆盖率阈值
bash ../scripts/e2e.sh # 一键 E2E（重置数据 + 起服务 + 跑 Playwright）
```

⚠️ E2E 跑 `vite preview`（生产构建）而不是 dev server：
dev server 每个请求现场转译模块，在小内存机器上会把整个套件拖垮——
表现是随机超时、每次红的用例都不一样，极容易被误判成「E2E 就是不稳定」。

---

## 9. 每个 tag 的完成定义

- [ ] `npm run typecheck && npm run build` 通过
- [ ] `npm run test` 全绿，新增逻辑有测试
- [ ] `npm run e2e` 全绿
- [ ] 🔒 `git diff main HEAD -- apps/rbac/services.py` 为空
- [ ] 后端 `pytest` 仍然全绿
- [ ] 权限常量与后端一致（`export_perm_constants --check`）
- [ ] 没有提前实现后续 tag 的内容
- [ ] 文档中与实现不符之处已同步更新
