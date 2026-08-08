# vue-v0.5.0 — 🔴 动态路由注册与导航守卫

| 项 | 值 |
| --- | --- |
| 需求 | VE-3.1、VE-3.2、VE-3.6、VE-3.7、**VE-3.8** |
| 关键 V-ADR | [004](../02-设计文档.md)、[005](../02-设计文档.md)、[013](../02-设计文档.md) |
| 预计耗时 | 3.5 ~ 4.5 小时 |
| 变更规模 | ~300 行 |
| 上一个 tag | `vue-v0.4.0` |
| React 对应 | [`fe-v0.7.0`](../../frontend/tags/07-fe-v0.7.0-动态路由与守卫.md) |

> 🔴 **本阶段最容易出 bug 的一个 tag，没有之一。**
> React 版在对应位置踩了 3 个时序 bug，Vue 版的时序陷阱**不一样但一样多**。

---

## 一、动手之前，先自己想清楚

1. Vue Router 有 `addRoute()` 但**没有** `setRoutes()`。这意味着什么？
2. `addRoute()` 之后，当前这次导航会自动重新匹配吗？**不会的话会发生什么？**
3. 用户登出，然后换一个权限更小的账号登录。**上一个账号的路由怎么办？**
4. 守卫里 `await` 一个网络请求，第二次导航进来会重复 await 吗？
5. 后端下发的 `component` 是 `"tickets/List"`，怎么变成 `import('@/pages/tickets/List.vue')`？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/router/registry.ts` | `component` 字符串 → 懒加载组件 |
| 新建 | `src/router/buildRoutes.ts` | 菜单树 → `RouteRecordRaw[]` |
| 新建 | `src/router/dynamic.ts` | 🔴 `registerDynamicRoutes` / **`clearDynamicRoutes`** |
| 新建 | `src/router/guard.ts` | 导航守卫 |
| 修改 | `src/router/index.ts` | 挂守卫，去掉写死的子路由 |
| 修改 | `src/pages/Login.vue` | 登出时调 `clearDynamicRoutes()` |

---

## 三、接口契约

```ts
// registry.ts
export function resolveComponent(component: string | null): (() => Promise<unknown>) | null

// buildRoutes.ts
export function buildRoutes(menus: MenuNode[]): RouteRecordRaw[]

// dynamic.ts
export function registerDynamicRoutes(menus: MenuNode[]): void
export function clearDynamicRoutes(): void          // 🔴 React 版没有这个函数
```

---

## 四、⚠️ 容易写错的地方

### 1. 第一节第 5 问：`import.meta.glob`，**两边逐字相同**

```ts
// ⚠️ 路径必须是**字面量**——Vite 做的是静态分析，拼接出来的路径它看不见，
//    modules 会是空对象，所有页面都加载不出来。
const modules = import.meta.glob('../pages/**/*.vue')

export function resolveComponent(component: string | null) {
  if (!component) return null
  const key = `../pages/${component}.vue`
  const loader = modules[key]
  if (!loader) {
    // 后端 component 配错了。**不能让整个应用崩**——降级成 null，
    // 由调用方渲染提示页，其余页面照常。
    console.error(`[router] 找不到组件：${key}（后端 component 字段配错了？）`)
    return null
  }
  return loader
}
```

> 📌 **这段代码和 React 版只差两个字符**（`.tsx` → `.vue`）。
>
> `import.meta.glob` 是 **Vite** 的能力，不是 React 或 Vue 的。
> 「后端下发组件名 → 前端懒加载」这个模式的实现，**与框架完全无关**。
>
> 而且 React 版注释里那句话在这里同样成立：
> > 这和 Tailwind 扫描不到拼接 class 名是同一类问题：
> > **构建工具做静态分析，运行时拼的东西它不知道。**

### 2. 🔴 第一节第 2 问：**不会**。这是刷新变 404 的 Vue 版形态

```ts
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (PUBLIC_ROUTES.includes(to.path)) return true

  if (auth.status === 'unknown') {
    try {
      await fetchProfileIntoStore()
    } catch {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    registerDynamicRoutes(auth.menus)

    // 🔴🔴 关键的一行，本 tag 的核心。
    //
    //   addRoute() 之后，参数 `to` 是**在旧路由表上算出来的**
    //   （大概率已经落到 404 兜底路由）。直接 return true 会渲染那个 404 ——
    //   这正是 F-ADR-007 描述的「刷新页面变 404」在 Vue 里的表现形式。
    //
    //   必须重新发起一次导航，让它在**新**路由表上重新匹配。
    //   replace: true 是为了不在历史里留下一条 404。
    return { ...to, replace: true }
  }

  if (to.meta.perm && !auth.can(to.meta.perm as PermCode)) return { path: '/403' }
  return true
})
```

**这行代码看起来像死循环。** 第一节第 4 问的答案说明它为什么不是：
第二次进来时 `auth.status` 已经不是 `'unknown'`，不会再进这个分支。

> ⚠️ **这个保证藏在另一个变量里，是整段代码最脆弱的地方。**
>
> `vue-v0.4.0` 陷阱 4 要求 `fetchProfileIntoStore()` **无论成功失败都把 status
> 置为终态**——如果那里没写对，这里就会无限重定向，
> Vue Router 抛 `Maximum recursive navigation guard calls`。
>
> **两个 tag 之外的一行代码决定这里循环不循环。** 这类耦合最值得警惕。

### 3. 🔴🔴 第一节第 1、3 问：`addRoute` 只能加，**必须自己清理**

**先写出有 bug 的版本，跑一遍，亲眼看到它。**（`03-实施计划.md` 第 5 节）

```ts
// ❌ 第一版：能跑，测试也过，但有 bug
export function registerDynamicRoutes(menus: MenuNode[]) {
  for (const record of buildRoutes(menus)) {
    router.addRoute('layout', record)
  }
}
```

**复现步骤（`VUS-6`）**：

```
1. superadmin 登录 → 注册了 /system/users 等全部路由
2. 登出
3. cs_staff 登录  → 注册了 /tickets
4. 地址栏输入 /system/users
   ❌ 进得去（路由还在）→ 页面空白 → 接口 403 → 控制台一片红
```

**它不是安全漏洞**（后端照样 403），**是功能 bug**——用户会以为系统坏了。

**修正**：

```ts
let registered: Array<() => void> = []

export function registerDynamicRoutes(menus: MenuNode[]) {
  clearDynamicRoutes()                                  // ⚠️ 先清，再加
  for (const record of buildRoutes(menus)) {
    registered.push(router.addRoute('layout', record))  // 返回移除函数
  }
}

export function clearDynamicRoutes() {
  // 🔴 登出、换账号后必须调。
  //    Vue Router 没有「重建路由表」这回事，只能一条条移除。
  //    React 版靠重建 router 天然获得这个行为，**不需要这个函数**——
  //    这是「增量 API」相对「重建 API」多出来的一类维护责任。
  registered.forEach((remove) => remove())
  registered = []
}
```

**为什么不用 `removeRoute(name)`**：它要求每条路由有唯一 `name`，
而菜单是后端下发的，`name` 由 `route_path` 派生——
**两个菜单指向同一组件时会撞名**，表现是「移除了不该移除的那条」，极难排查。
`addRoute` 的返回值不依赖 name，是精确的。

> 🔴 [04 对比文档第 6 节](../04-React与Vue3做法对比.md#6-动态路由注册重建-vs-增量)：
>
> > **「增量 API」比「重建 API」多欠一笔债，而这笔债不会主动来找你。**
> > 它只在「第二次」才暴露：第二次登录、第二个账号、第二次权限变更。
> > 而开发时你几乎总是在测「第一次」。

### 4. 别用 `vue-router/auto`（文件式路由）

```ts
// ❌ 与本项目架构根本冲突
import { createRouter } from 'vue-router/auto'
```

理由见 [V-ADR-013](../02-设计文档.md)。一句话：
**文件式路由的真相源是文件系统，本项目的真相源是后端数据库。**

**最硬的证据**：Vue Router 5 的 experimental router（配合文件式路由设计的那个）
在类型定义里写着：

> This router does not have `addRoute()` and `removeRoute()` methods
> and is meant to be used with file-based routing.

**它直接删掉了动态路由 API。** 不是巧合——
**文件式路由和动态注册是互斥的两种世界观。**

### 5. 守卫必须极简、且只有那一次副作用

```ts
// ❌ 不要在守卫里做这些
router.beforeEach(async (to) => {
  await logPageView(to)          // 埋点 → 每次导航多一个请求
  await refreshSomething()       // 任何额外的 await 都让导航变慢
})
```

所有导航都要过这个守卫。除了「第一次拉 profile」，**不该有任何别的副作用**。

⚠️ 已知简化 #10：页面多了之后应拆成多个守卫（认证 / 权限 / 埋点）并明确顺序。
本项目保持单个守卫，因为拆开会让 diff 讲两件事。

### 6. `403` vs `404`：`knownRoutes` 的用途

用户输入一个不在自己路由表里的路径，该给哪个？

```ts
// 后端下发的 knownRoutes 是**全部**菜单路径（含无权限的）
if (auth.knownRoutes.some((r) => to.path === r || to.path.startsWith(r + '/'))) {
  return { path: '/403' }        // 路径存在，你没权限
}
return { path: '/404' }          // 路径根本不存在
```

⚠️ 注意 `startsWith(r + '/')` 的斜杠——不加的话 `/tickets-archive`
会被误判为 `/tickets` 的子路径。

> **这和后端部门树 `path` 尾斜杠是同一类陷阱**（`v0.3.0` 陷阱 1、
> `fe-v0.8.0` 陷阱 4）。**字符串前缀匹配必须带分隔符。**
> 同一个坑，**第四次**出现了。

### 7. 全局 loading：守卫是异步的

`vue-v0.3.0` 挂的位置现在接上：

```ts
router.beforeEach(() => { ui.navigating = true })
router.afterEach(() => { ui.navigating = false })
router.onError(() => { ui.navigating = false })    // ⚠️ 别忘了错误分支
```

⚠️ 漏掉 `onError` 的表现是「导航失败后 spinner 永远转」。

### 8. ⚠️⚠️ 守卫不是安全边界

在 `guard.ts` 顶部写一段注释，**内容与 React 版 `PermissionGate.tsx` 等价**：

```ts
/**
 * ⚠️⚠️ 这不是安全边界。
 *
 *    perms 就在用户的浏览器内存里，Vue Devtools 里改成 ['*'] 只需要几秒；
 *    而且攻击者根本不必用这个前端——他可以直接 curl 你的 API。
 *
 *    ⚠️ Vue 的守卫拦在**导航期**，页面组件根本不会被创建，
 *       写出来也更像真正的鉴权：
 *
 *           if (!can(to.meta.perm)) return '/403'
 *
 *       **正因为它更像，错觉更强。** 拦得早 ≠ 拦得住。
 *       唯一决定安全的是「拦在哪一侧」，不是「拦在哪一步」。
 *
 *    唯一的安全边界是后端的 HasPerm + ScopedQuerysetMixin。
 *    vue-v0.14.0 会用与 React 版**逐字相同**的 E2E 证明这一点。
 */
```

---

## 五、卡住了看这里

<details>
<summary><b>提示：buildRoutes</b></summary>

```ts
export function buildRoutes(menus: MenuNode[]): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = []
  const walk = (nodes: MenuNode[]) => {
    for (const node of nodes) {
      if (node.routePath && node.component) {
        const loader = resolveComponent(node.component)
        routes.push({
          path: node.routePath.replace(/^\//, ''),   // 相对父路由
          component: loader ?? MisconfiguredPage,
          // 守卫是**兜底**不是主力：能走到这里说明后端已经把这个菜单
          // 下发给了当前用户，正常情况下必然通过。
          meta: { perm: node.permCode ?? null },
        })
      }
      walk(node.children)     // catalog 节点本身不产生路由
    }
  }
  walk(menus)
  return routes
}
```
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 登录后点菜单 | 正常进入 |
| 2 | 🔴 在 `/tickets` **按 F5** | 停在 `/tickets`，**不是 404** |
| 3 | 🔴 在 `/tickets/42` 按 F5 | 同上 |
| 4 | `cs_staff` 地址栏输入 `/system/users` | **403 页面** |
| 5 | 输入 `/zzz`（根本不存在） | **404 页面**（不是 403） |
| 6 | 未登录访问 `/tickets` | 跳 `/login?redirect=/tickets`，登录后回来 |
| 7 | 🔴🔴 **`superadmin` 登录 → 登出 → `cs_staff` 登录 → 输入 `/system/users`** | **403**（做修正前应该是「进得去但空白」） |
| 8 | 把 `fetchProfileIntoStore` 的 catch 里的 `auth.reset()` 删掉，断网 | **无限重定向报错**（看一次，再改回来） |
| 9 | 后端把某个 `component` 改成不存在的值 | 那一个页面显示提示，**其余页面照常** |
| 10 | `no_role` 登录 | 首页有说明文案，不白屏 |
| 11 | 导航过程中 | 有 loading，不是「点了没反应」 |
| 12 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 7 和 8 是本 tag 的灵魂。**
请先做出 bug 版本、亲眼看到现象，再修正——
用例 7 的 bug 在 React 版**根本不会出现**，不主动制造就永远遇不到。

---

## 七、和我的实现对比什么

```bash
diff -u frontend/src/router/registry.ts frontend-vue/src/router/registry.ts   # 期望：只差后缀
git diff vue-v0.4.0 vue-v0.5.0 -- frontend-vue/src/router/
```

| 对比点 | 想一想 |
| --- | --- |
| `registry.ts` 差了几个字符 | 差很多的话，你把 Vite 的能力当成框架的能力了？ |
| 有没有 `clearDynamicRoutes` | 没有的话跑用例 7 |
| 守卫里除了 profile 还 await 了什么 | 每多一个，所有导航都慢一点 |
| `startsWith` 加斜杠了吗 | 造一个 `/tickets-archive` 试试 |
| `onError` 里复位 loading 了吗 | 跑用例 8 时会发现 |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `registry.ts`（`import.meta.glob`） | 🟢 **只差文件后缀**（这是 Vite 的能力） |
| `buildRoutes` | 🟡 同构：返回 `RouteRecordRaw[]` ← `RouteObject[]` |
| **注册方式** | 🔴🔴 `addRoute()` 增量 ← 重建整个 router |
| **清理** | 🔴🔴 **必须手写 `clearDynamicRoutes`**；React **不需要** |
| **守卫位置** | 🔴 导航期 `beforeEach` ← 渲染期 `<PermissionGate>` |
| **刷新时序的解法** | 🔴 `return {...to, replace:true}` ← 「profile 没到就不渲染 router」 |
| 失败模式 | 🔴 **无限重定向（抛异常）** ← **死锁（静默转圈）** |
| 403/404 分流 | 🟢 逻辑相同（`knownRoutes` 前缀匹配） |
| 文件式路由 | 🔴 **Vue 有这条岔路，且必须不走**（V-ADR-013） |

**这个 tag 是两个框架差异最大的地方。**
[04 对比文档](../04-React与Vue3做法对比.md)总账里「真正 Vue 特有的 6 条决策」，
另外 3 条（004 / 005 / 013）全在这里。

---

## 九、延伸思考

1. React 版在对应位置踩了 3 个时序 bug（刷新变 404、`useMemo` 依赖导致
   router 反复重建、403 与 404 分不清）。**Vue 版踩了几个？是同样的三个吗？**
   不一样的地方，能归因到哪条设计差异？

2. 用例 7 的 bug **只在「第二次」才出现**。
   你的项目里还有哪些「只在第二次才暴露」的问题？
   **有没有一种系统性的办法在开发期就覆盖到它们？**

3. `return { ...to, replace: true }` 的不循环保证，依赖两个 tag 之外的一行代码。
   **这算好设计吗？** 如果不算，怎么改能让这个保证是局部的、自明的？

4. 现在四层体验已经完成两层（守卫、还差菜单和按钮）。
   用 `cs_staff` 登录，打开 Vue Devtools 把 `auth.perms` 改成 `['*']`，
   **然后手动输入 `/system/users`。** 发生了什么？
   **和 React 版需要挂 `window.__AUTH_STORE__` 相比，这说明了什么？**
