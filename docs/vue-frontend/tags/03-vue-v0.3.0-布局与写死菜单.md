# vue-v0.3.0 — 后台布局与**写死的**菜单 ⚠️

| 项 | 值 |
| --- | --- |
| 需求 | — |
| 关键 V-ADR | — |
| 预计耗时 | 2 ~ 3 小时 |
| 变更规模 | ~250 行 |
| 上一个 tag | `vue-v0.2.0` |
| React 对应 | [`fe-v0.4.0`](../../frontend/tags/04-fe-v0.4.0-布局与写死菜单.md) |

> ⚠️ **本 tag 刻意留下一个不安全的中间态：菜单是写死的，没有任何权限判断。**
>
> 这是第三次用同一个手法（后端 `v0.8.0`、React `fe-v0.4.0`、这里）。
> 目的相同：让 `vue-v0.5.0` / `vue-v0.6.0` 的 diff **只讲权限这一件事**。
>
> **不要提前加守卫。** 你已经知道最终答案了，这让越界的诱惑在本阶段格外大。

---

## 一、动手之前，先自己想清楚

1. 写死的菜单要写在哪里？写在 `Sidebar.vue` 里可以吗？
2. 布局组件和路由怎么配合？Vue Router 的**嵌套路由**和 React Router 的
   `<Outlet />` 是什么关系？
3. 用 `cs_staff` 登录，他会看到「用户管理」这个菜单项吗？**点进去会怎样？**

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/layouts/AdminLayout.vue` | 侧边栏 + 顶栏 + `<RouterView>` |
| 新建 | `src/layouts/Sidebar.vue` | ⚠️ **写死**的菜单 |
| 新建 | `src/layouts/Topbar.vue` | 用户名 + 登出 |
| 新建 | `src/layouts/PageContainer.vue` | 页面标题 + 内容槽 |
| 新建 | `src/pages/Forbidden.vue` / `NotFound.vue` | 403 / 404 |
| 新建 | `src/pages/tickets/List.vue` 等 | **占位页**（一句话即可） |
| 新建 | `src/store/uiStore.ts` | 侧边栏折叠状态 |
| 修改 | `src/router/index.ts` | 嵌套路由：layout 作为父，页面作为子 |

---

## 三、路由结构

第一节第 2 问：Vue Router 用**嵌套路由**，父路由的组件里放 `<RouterView />`。

```ts
// src/router/index.ts
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/pages/Login.vue') },
    {
      path: '/',
      // ⚠️ name 很重要：vue-v0.5.0 的 addRoute('layout', ...) 要用它当父节点
      name: 'layout',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        // 本 tag 先写死几条，vue-v0.5.0 改成动态注册
        { path: 'tickets', component: () => import('@/pages/tickets/List.vue') },
        { path: 'system/users', component: () => import('@/pages/system/Users.vue') },
        { path: '403', component: () => import('@/pages/Forbidden.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', component: () => import('@/pages/NotFound.vue') },
  ],
})
```

### 📌 与 React 版的对照

| | React Router | Vue Router |
| --- | --- | --- |
| 嵌套 | `<Route element={<AdminLayout/>}>` 包住子 `<Route>` | `children: [...]` |
| 子路由出口 | `<Outlet />` | `<RouterView />` |
| 兜底 | `path="*"` | `path: '/:pathMatch(.*)*'` |

🟡 **同构改写。** 概念一一对应，只有写法不同。

⚠️ Vue 的兜底路由语法 `'/:pathMatch(.*)*'` 很容易写错（少一个 `*`、
少括号）。写错的表现是**404 页面永远不出现**，所有未匹配路径白屏。

---

## 四、⚠️ 容易写错的地方

### 1. 写死的菜单要放在一个显眼的常量里

```ts
// src/layouts/Sidebar.vue
//
// ⚠️⚠️ 写死的菜单，vue-v0.6.0 会整个删掉换成后端下发。
//      **这是刻意的中间态，不是遗漏。**
//      现在每个用户看到的菜单完全一样——包括他进不去的那些。
const HARDCODED_MENUS = [
  { key: '/tickets', label: '工单管理' },
  { key: '/system/users', label: '用户管理' },
]
```

放在组件顶部 + 大写常量名 + 显眼注释。这样 `vue-v0.6.0` 的 diff 里
「删掉这一块，换成 `auth.menus`」讲的就是一件干净的事。

### 2. 第一节第 3 问：会看到，点进去是空占位页

**这正是本 tag 要让你看见的。**

用 `cs_staff` 登录，侧边栏赫然有「用户管理」。点进去——不是 403，
是一个空白的占位页。因为：

- 没有守卫（`vue-v0.5.0` 才有）
- 没有真实接口调用（`vue-v0.10.0` 才有）

到 `vue-v0.10.0` 接上真实接口后，同样的操作会变成「页面进得去，
表格一片空白，控制台 403」。**那才是最糟糕的用户体验**——
比直接 403 页面糟得多，因为用户不知道发生了什么。

> 记住这个画面。`vue-v0.5.0` 和 `vue-v0.6.0` 就是为了消灭它。

### 3. 侧边栏折叠状态属于 `uiStore`，不属于 URL

| 数据 | 归属 |
| --- | --- |
| 侧边栏折叠 | 客户端状态 → **Pinia `uiStore`** |
| 分页 / 筛选 | 属于**地址** → URL search params（`vue-v0.8.0`） |
| 工单列表 | 服务端状态 → vue-query（`vue-v0.8.0`） |

⚠️ 这三条线不能混。混了的表现：刷新后筛选条件丢失、链接分享出去看到的不是同一个列表。

### 4. `AdminLayout` 里**不要**做认证判断

```vue
<!-- ❌ 本 tag 不该有这个 -->
<template>
  <div v-if="auth.status === 'authenticated'">...</div>
</template>
```

认证与权限的拦截统一放在 `vue-v0.5.0` 的导航守卫里。
在布局组件里判断会造成两处实现，而且两处的规则迟早不一致
（后端 `CLAUDE.md` 安全红线第 5 条的前端形态）。

### 5. 全局 loading 条要现在就加

`vue-v0.5.0` 的守卫是 `async` 的，profile 慢的时候用户会看到「点了没反应」。
现在先在 `AdminLayout` 里挂一个进度条的位置，下个 tag 接上。

```vue
<a-spin :spinning="uiStore.navigating" :delay="200">
  <RouterView />
</a-spin>
```

⚠️ `:delay="200"` 不能少——不加的话每次导航都闪一下 spinner，比不加还难受。

### 6. 🔴📌 父路由有 `name`，空路径子路由**必须也有 `name`**（实测踩到）

```ts
{
  path: '/',
  name: 'layout',                 // vue-v0.5.0 的 addRoute('layout', ...) 要用
  children: [
    { path: '', redirect: '/tickets' },      // ❌ 登录后停在原地
    { path: '', name: 'home', redirect: '/tickets' },  // ✅
  ],
}
```

**症状**：登录成功（接口 200、store 也更新了），但**页面停在登录页**，
看起来像「按钮点了没反应」。

**原因**：导航到 `/` 时命中的是**父路由的 name**，空路径子路由不会被渲染。
Vue Router 5 会打一条警告说明这件事：

```
[VUE_ROUTER_R0103] The route named "layout" has a child without a name,
an empty path, and no children. Using that name won't render the empty path child…
```

⚠️ **它只是 `console.warn`，不会让任何东西失败**，很容易被忽略——
而症状（登录没反应）和原因（路由命名）离得非常远。

> 📌 这个坑的成因很有意思：**父路由的 `name` 是为 `vue-v0.5.0` 准备的**
> （`addRoute` 必须能指名道姓地找到父节点），
> 而它在**当下**制造了一个 bug。
>
> React Router 不需要给节点起名——它的动态路由是「重新构造整棵树」，
> 父子关系由 JSX 嵌套表达。**「增量 API 需要节点有身份」这个要求，
> 顺带带来了一类 React 不会有的错误。**

### 7. 🔴📌 antdv 的 `Menu` **没有** `defaultOpenKeys`（实测踩到）

React（antd 6）：

```tsx
<Menu defaultOpenKeys={['ticket', 'system', 'monitor']} ... />
```

照抄成 `:default-open-keys="[...]"` 在 antdv 里是个**未声明的 prop**——
它会掉进 `$attrs` 落到根元素上，**不报错、不警告、也不生效**。

**症状**：所有子菜单默认收起。「部门管理」在 DOM 里但不可见——
E2E 点不到才暴露，肉眼扫一眼页面很容易以为「设计如此」。

**修正**：antdv 只提供受控的 `openKeys`，非受控的默认值要自己给初始值。

```vue
<script setup lang="ts">
const openKeys = ref<string[]>(['ticket', 'system', 'monitor'])
</script>
<template>
  <Menu v-model:open-keys="openKeys" ... />
</template>
```

⚠️ 这也正好是 `vue-v0.6.0` 要的形态（那里要做「自动展开当前项的父目录，
但不覆盖用户手动折叠」的并入逻辑）。

> 📌 **这已经是本阶段第 4 次「照抄 React 版写出无效属性」**：
>
> | tag | 位置 | 类型 |
> | --- | --- | --- |
> | `vue-v0.2.0` | `ConfigProvider` 的 `autoInsertSpace` | 换了名字 |
> | `vue-v0.2.0` | `Spin` 的 `tip` / `description` | 换了名字 |
> | `vue-v0.3.0` | `Menu` 的 `defaultOpenKeys` | **能力压根不存在** |
> | `vue-v0.10.0` | `Modal` 的 `destroyOnClose` | 换了名字（尚未遇到） |
>
> **共同点：Vue 的模板对未知属性是宽容的**（透传到 `$attrs`），
> 而 React 的 TSX 对未知 prop 会**编译期报错**。
>
> 这是 JSX 相对模板在这一点上实打实的优势，
> 与「Vue vs React 谁更好」无关——**它只是类型检查边界的位置不同**。
> ⚠️ 也要看到反面：正因为宽容，Vue 的模板才能把任意属性透传给子组件，
> 这在封装第三方组件时省掉大量样板。

### 8. `Spin` 的提示文案：antdv 用 `tip`

```vue
<!-- ✅ antdv 4 -->
<a-spin tip="正在加载" />
```

⚠️ React 版 antd 6 里 `tip` 已废弃，要用 `description`。
**照抄 React 版会写出一个无效属性**——和 `vue-v0.2.0` 陷阱 3 同一类问题，
本阶段第二次出现。

> 📌 规律：**从 antd 6 往 antdv 4 抄，等于从新版本往旧版本抄。**
> 凡是 React 版注释里写着「XXX 已废弃，用 YYY」的地方，
> Vue 版**大概率要用回那个 XXX**。遇到就查一次文档，别凭记忆。

---

## 五、卡住了看这里

<details>
<summary><b>提示：AdminLayout.vue</b></summary>

```vue
<script setup lang="ts">
import { useUiStore } from '@/store/uiStore'
const ui = useUiStore()
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider v-model:collapsed="ui.collapsed" collapsible>
      <Sidebar />
    </a-layout-sider>
    <a-layout>
      <a-layout-header><Topbar /></a-layout-header>
      <a-layout-content style="margin: 16px">
        <!-- 子路由出口，对应 React 的 <Outlet /> -->
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>
```
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 登录后 | 看到侧边栏 + 顶栏 + 内容区 |
| 2 | 点菜单 | URL 变化，内容区切换 |
| 3 | 刷新 | 停在当前页（不跳首页） |
| 4 | 折叠侧边栏 | 只剩图标 |
| 5 | 访问不存在的路径 `/zzz` | **404 页面**（不是白屏） |
| 6 | ⚠️ 用 `cs_staff` 登录 | **能看到「用户管理」**，点进去是空占位页 |
| 7 | 顶栏登出 | 回登录页 |
| 8 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 6 现在是「通过」的**——这是刻意中间态。
`vue-v0.6.0` 之后它的期望会反过来：**看不到**。

---

## 七、和我的实现对比什么

| 对比点 | 想一想 |
| --- | --- |
| 写死的菜单在一个显眼常量里吗 | 散在模板里的话，`vue-v0.6.0` 的 diff 会很脏 |
| 布局里有没有偷偷加权限判断 | 加了的话，你已经越界了 |
| 兜底路由语法写对了吗 | 跑用例 5 |
| `Spin` 用的是 `tip` 还是 `description` | 用后者的话，控制台会有警告吗？（**可能没有**） |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| 布局结构 | 🟢 **无差异**（同一套 antd Layout 组件） |
| 嵌套路由 | 🟡 同构：`children` + `<RouterView>` ← `<Route>` 嵌套 + `<Outlet>` |
| 兜底路由语法 | 🟡 `':pathMatch(.*)*'` ← `path="*"`（Vue 更容易写错） |
| 折叠状态 | 🟡 `ui.toggleSider()` ← 受控 prop + onChange |
| `uiStore` 持久化 | 🟡 手写 5 行 ← Zustand 自带 `persist` 中间件 |
| `PageContainer` 的复用 | 🟡 插槽 ← `children` + `extra` prop（模板版是继承，三种手法） |
| **空路径子路由要有 `name`** | 🔴📌 **实测踩到**（陷阱 6）。React 无此概念 |
| **`Menu` 没有 `defaultOpenKeys`** | 🔴📌 **实测踩到**（陷阱 7）。第 4 次「照抄写出无效属性」 |
| **`ErrorResult` 的「可选回调 prop」** | 🔴 Vue 里**没有直译**：`defineEmits` 声明过的事件会从 `$attrs` 摘掉，`v-if="$attrs.onRetry"` 恒为 false。要拆成 `retryable` + `@retry` |
| `Spin` 的提示 prop | 🔴 `tip` ← `description`（**UI 库版本世代**差异） |
| 刻意中间态的手法 | 🟢 **完全相同**（第三次使用） |

**本 tag 的结论**：布局的**结构**完全同构——概念一一对应，没有一处需要重新设计。

但它挖出了**两个真 bug 和一个不能直译的惯用法**，共同点值得记：

> **它们全都编译通过、全都不报错、全都要靠跑起来才发现。**
>
> - 空路径子路由没 name → 只有一条 `console.warn`
> - `defaultOpenKeys` → 静默落进 `$attrs`
> - `$attrs.onRetry` → 恒为 false
>
> 三处的根因是同一个：**Vue 的模板层对「多余的东西」是宽容的**。
> 宽容换来了透传的便利，代价是这类错误逃过了编译期。

---

## 九、延伸思考

1. 这是「写死菜单」这个手法的第三次使用（`v0.8.0` → `fe-v0.4.0` → 本 tag）。
   **三次的目的完全一样吗？** 如果一样，为什么每次都要重来一遍，
   而不是直接从上一个前端把最终版抄过来？

2. 用例 6 揭示的问题在 Django 模板版**根本不存在**——模板版从 `v0.10.0`
   起就是服务端渲染，没权限的菜单压根不会进 HTML。
   **SPA 为什么天然会有这个中间态？** 它是实现顺序的问题，还是架构的必然？

3. 现在两个 SPA 的布局几乎一模一样。
   **如果把 `AdminLayout` 做成 Web Component 让两边共用，会有什么问题？**
   （提示：菜单要读 store，而两边的 store 不是同一个东西。）
