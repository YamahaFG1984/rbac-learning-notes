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

### 6. `Spin` 的提示文案：antdv 用 `tip`

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
| 兜底路由语法 | 🟡 `'/:pathMatch(.*)*'` ← `path="*"`（Vue 更容易写错） |
| 折叠状态 | 🟡 `v-model:collapsed` ← 受控 prop + onChange |
| `uiStore` | 🟡 Pinia ← Zustand |
| `Spin` 的提示 prop | 🔴 `tip` ← `description`（**UI 库版本世代**差异） |
| 刻意中间态的手法 | 🟢 **完全相同**（第三次使用） |

**本 tag 的结论**：布局层是「同构改写」的典型——概念一一对应，
**没有任何一处需要重新设计**。

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
