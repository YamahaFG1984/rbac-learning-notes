# React 与 Vue 3：同一件事的两种做法

| 项 | 值 |
| --- | --- |
| 文档版本 | v1.0（骨架定稿；📌 标记的实测结论在 `vue-v1.0.0` 回填） |
| 状态 | 随实现推进持续更新 |
| 最后更新 | 2026-08-08 |
| 关联文档 | [01-PRD.md](01-PRD.md)、[02-设计文档.md](02-设计文档.md)、[03-实施计划.md](03-实施计划.md) |

---

## 0. 这份文档怎么读

**这不是「Vue vs React 谁更好」。** 那种对比没有价值，因为它脱离具体问题。

这份文档的前提是一个**受控实验**：

| 控制住的变量 | 说明 |
| --- | --- |
| 后端 | 完全相同，一行不改 |
| 需求 | 同一份 PRD，编号一一对应（`FE-1.1` ↔ `VE-1.1`） |
| 构建 / HTTP / 测试工具 | Vite、axios、TanStack Query、Vitest、MSW、Playwright **同库同版本**（[V-ADR-002](02-设计文档.md)） |
| E2E 断言值 | 80 / 50 / 5 条，逐格相同 |
| 实现者 | 同一个人，间隔很短 |

在这种条件下，**两边写法不同的地方，差异必然来自框架本身**。

### 每一节的固定结构

```
问题是什么  →  React 怎么写  →  Vue 怎么写  →  差异的实质  →  各自会踩的坑
```

> ⚠️ 最后一栏「各自会踩的坑」是本文档最有价值的部分。
> 「哪个写起来更短」几乎没有信息量；**「哪个更容易写出不报错的错误代码」才有。**

### 一句话总纲

> **React 的模型让你很难写出「该更新却不更新」的代码，代价是要手动阻止过度更新；
> Vue 的模型让你很难写出「过度更新」的代码，代价是要显式声明响应式边界。**
>
> **两边的 bug 方向恰好相反，而且都不报错。**

本文档会反复回到这一句。

---

## 目录

| # | 主题 | 差异程度 |
| --- | --- | --- |
| [1](#1-响应式模型不可变重渲染--可变代理依赖追踪) | 响应式模型 | 🔴 根本 |
| [2](#2-权限-store-zustand--pinia) | 权限 store | 🔴 大 |
| [3](#3-在组件外访问-store拦截器) | 组件外访问 store | 🔴 **Vue 独有的问题** |
| [4](#4-权限判断函数-usepermission) | 权限判断函数 | 🟡 小 |
| [5](#5-按钮级权限can-组件与-vue-独有的指令诱惑) | 按钮级权限 + **指令之争** | 🔴 **Vue 多一条岔路** |
| [6](#6-动态路由注册重建-vs-增量) | 动态路由注册 | 🔴 大 |
| [7](#7-路由守卫渲染期-vs-导航期) | 路由守卫的位置 | 🔴 大 |
| [8](#8-刷新页面变-404同一个陷阱两种解法) | 刷新变 404 的时序陷阱 | 🔴 大 |
| [9](#9-服务端状态-tanstack-query-的两个适配层) | TanStack Query 两个适配层 | 🔴 **静默失效点** |
| [10](#10-分页与筛选同步到-url) | 分页筛选同步 URL | 🟡 小 |
| [11](#11-把-query-的结果写进-store一个跨框架的时序陷阱) | Query → store 的同步 | 🔴 **踩过的坑** |
| [12](#12-错误边界react-唯一的-class-vs-vue-的两个钩子) | 错误边界 | 🟡 实现不同、**限制相同** |
| [13](#13-表单受控组件-vs-v-model) | 表单 | 🟡 小 |
| [14](#14-测试两种相反的隔离麻烦) | 测试 | 🟡 方向相反 |
| [15](#15-e2e一个字都不用改) | E2E | 🟢 **无差异（这是结论）** |
| [16](#16-ui-库的接入方式全局注册-vs-按需-import) | UI 库的接入方式 | 🔴 **Vue 的默认写法有体积陷阱** |
| [17](#17-总账哪些与框架无关) | 总账 | — |

---

## 1. 响应式模型：不可变+重渲染 / 可变代理+依赖追踪

**这一节是后面所有差异的根源。** 先看清它，后面 14 节都是它的推论。

### React：函数每次重新执行，值每次重新求

```tsx
function TicketList() {
  const perms = useAuthStore((s) => s.perms)     // 组件函数**每次渲染都重跑**
  const canDelete = perms.includes('ticket:ticket:delete')   // 每次重算
  const columns = [...base, ...(canDelete ? [delCol] : [])]  // 每次重建
  return <Table columns={columns} />
}
```

「更新」的机制是：**整个函数重新执行一遍，产出一份新的描述**。

### Vue：`<script setup>` 只执行一次，靠依赖追踪

```vue
<script setup lang="ts">
const auth = useAuthStore()                                  // ⚠️ **只执行一次**
const canDelete = computed(() => auth.perms.includes('ticket:ticket:delete'))
const columns = computed(() => [...base, ...(canDelete.value ? [delCol] : [])])
</script>

<template><a-table :columns="columns" /></template>
```

「更新」的机制是：**函数不再执行，被追踪到的依赖变了，只有依赖它的那部分重新求值**。

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 组件函数执行次数 | 每次更新一次 | **一次** |
| 派生值默认行为 | 每次重算（**总是新的**） | 不重算（**要显式 `computed`**） |
| 优化方向 | 用 `useMemo` **阻止**重算 | 用 `computed`/`watch` **启用**重算 |
| 写漏了会怎样 | 性能问题（重算太多） | **功能问题（该更新的不更新）** |

### 🔴 各自的失误模式（本项目真实踩过 / 会踩到的）

**React 的失误：`useMemo` 依赖数组写错 → 反复重建**

`fe-v0.7.0` 真实踩过。`AppRouter.tsx` 里留着当时的注释：

```tsx
// useMemo 用**内容指纹**做依赖，不用 menus 数组本身。
// Zustand 的 selector 返回数组时引用可能变，直接依赖会导致
// 路由表每次渲染都重建——表现是「输入框每敲一个字就失焦」。
const fingerprint = useMemo(() => { /* 把菜单树摊成字符串 */ }, [menus])
const dynamicRoutes = useMemo(() => buildRoutes(menus), [fingerprint])
```

**症状与原因隔了很远**：输入框失焦 → 组件被卸载重建 → 路由表变了 → `useMemo` 依赖的数组引用每次都新。中间隔着四层。

**Vue 的失误：忘了 `computed`，值定死不动**

```vue
<script setup lang="ts">
const auth = useAuthStore()
// ❌ 求值一次就定死了。权限变更后（vue-v0.11.0）这个值**永远不会更新**
const canDelete = auth.perms.includes('ticket:ticket:delete')
</script>
```

**没有任何报错**，第一次渲染还是对的。只有在「权限运行时变化」这个特定场景下才暴露——
而那正好是本项目 `VE-5.2` 的核心需求。

### 📌 一句话对照

| | 忘了写的后果 | 什么时候暴露 |
| --- | --- | --- |
| React 忘了 `useMemo` | 更新**太多** | 性能变差、输入框失焦 |
| Vue 忘了 `computed` | 更新**太少** | 权限变更时按钮不消失 |

**在权限系统里，Vue 的失误方向更危险**——「按钮该消失却没消失」是功能 bug，
而「多重渲染几次」只是慢。

> ⚠️ 但反过来说：React 的失误在**每个页面**都可能发生，Vue 的失误只在
> **状态运行时变化**的地方发生。频率和严重度是反过来的。
> **这就是为什么不能简单说谁更好。**

---

## 2. 权限 store：Zustand / Pinia

### React（Zustand）

```ts
// src/auth/store.ts —— 真实代码
export const useAuthStore = create<AuthState>((set) => ({
  ...EMPTY,
  status: 'unknown',
  setProfile: (profile) => set({ ...profile, status: 'authenticated' }),
  reset: () => set({ ...EMPTY, status: 'anonymous' }),
}))

// 组件里：必须传 selector，否则任何字段变化都会重渲染
const perms = useAuthStore((s) => s.perms)
```

### Vue（Pinia）

```ts
// src/auth/store.ts
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const perms = ref<string[]>([])
  const menus = ref<MenuNode[]>([])
  const knownRoutes = ref<string[]>([])
  const status = ref<'unknown' | 'authenticated' | 'anonymous'>('unknown')

  // ⚠️ 判断逻辑放在 store 里，<Can>、守卫、菜单都调这一个（同 F-ADR-009）
  const can = (code: PermCode) => perms.value.includes('*') || perms.value.includes(code)

  function setProfile(p: Profile) { /* ... */ status.value = 'authenticated' }
  function reset() { /* ... */ status.value = 'anonymous' }

  return { user, perms, menus, knownRoutes, status, can, setProfile, reset }
})

// 组件里：不需要 selector
const auth = useAuthStore()
// ⚠️ 但解构会丢响应性，要用 storeToRefs
const { perms, status } = storeToRefs(auth)
```

### 差异的实质

| | Zustand | Pinia |
| --- | --- | --- |
| 实例 | **模块级单例** | 绑在 app 实例上 |
| 订阅粒度 | 靠 selector **手动**指定 | 自动追踪，用到哪个订阅哪个 |
| 忘了细化订阅 | 整个组件重渲染（性能） | — |
| 解构 | `const { perms } = useAuthStore()` **会订阅全部** | `const { perms } = auth` **丢响应性**（值不再更新） |
| 组件外访问 | `useAuthStore.getState()` 随时可用 | 🔴 有时序限制，见第 3 节 |
| 单测隔离 | 手动 `setState(initial)` reset | 手动 `setActivePinia(createPinia())` |

### 🔴 各自的失误模式

**React**：忘了写 selector

```tsx
const { perms } = useAuthStore()   // ⚠️ 订阅整个 store，menus 变了也重渲染
const perms = useAuthStore((s) => s.perms)   // ✅
```
后果：性能。**不影响正确性。**

**Vue**：忘了 `storeToRefs`

```ts
const { perms } = useAuthStore()   // ⚠️ perms 是一个**普通数组**，之后永远不更新
const { perms } = storeToRefs(useAuthStore())   // ✅ Ref<string[]>
```
后果：**权限变更后按钮不消失。功能 bug。**

> 又是第 1 节那句话的实例：**同一个疏忽，React 侧是性能问题，Vue 侧是正确性问题。**

### ⚠️ 一个容易误判的点

`<template>` 里直接写 `auth.perms` 是**对的**（模板里的属性访问天然被追踪），
只有在 `<script setup>` 里解构才有问题。

这造成一个很坑的现象：**同一份代码，写在模板里能用，抽成 script 里的变量就失效了**。
而「把模板里的表达式抽成变量」是最常见的重构动作之一。

---

## 3. 在组件外访问 store（拦截器）

**🔴 这是 Vue 版新增的、React 版根本不存在的一个问题。**（`VE-2.6` / [V-ADR-003](02-设计文档.md)）

### React：没有这个问题

```ts
// src/api/versionWatcher.ts —— 真实代码，模块顶层 import，函数里直接用
import { useAuthStore } from '@/auth/store'

export async function watchRbacVersion(response: AxiosResponse) {
  const before = useAuthStore.getState().perms      // ✅ 组件外，随便调
  ...
}
```

Zustand 的 store 是模块级单例，`getState()` 是纯函数调用。**不需要任何额外设计。**

### Vue：会抛错

```ts
// ❌ 模块顶层执行 → 此时 app.use(pinia) 还没跑
const auth = useAuthStore()
// [🍍]: "getActivePinia()" was called but there was no active Pinia. Are you trying to use a store before calling "app.use(pinia)"?

client.interceptors.request.use((config) => {
  config.headers['X-CSRFToken'] = auth.csrfToken
})
```

**解法：把调用挪进函数体**

```ts
// ✅ src/api/client.ts
//
// ⚠️ useAuthStore() **必须**写在函数体内，不能提到模块顶层。
//    这个文件在 main.ts 里被 import，而那时 app.use(pinia) 还没执行。
//    提到顶层的表现是应用直接白屏，报错是
//    「getActivePinia() was called with no active Pinia」——
//    ⚠️ 实测：Pinia 4 的报错**明确指向了时机**（"before calling app.use(pinia)"），
//       比预想的有帮助。表现是整页白屏——失败得很响，容易修。
client.interceptors.request.use((config) => {
  const auth = useAuthStore()      // 拦截器**执行**时，app 早已挂载
  ...
})
```

需要触发副作用（跳登录页、invalidate query）时，两边**用完全相同的注入模式**：

```ts
// React（真实代码）                    // Vue（形状完全相同）
let onUnauthenticated: (() => void) | null = null
export function setUnauthenticatedHandler(h: () => void) { onUnauthenticated = h }
```

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| store 的生命周期 | **模块**（import 即存在） | **应用实例**（`app.use(pinia)` 之后才存在） |
| 组件外读取 | 直接 | 必须延后到运行期 |
| 多实例（SSR / 多测试用例） | 会串（模块单例） | 天然隔离 |

> **Pinia 的限制不是缺陷，是取舍**：它换来的是「store 跟随应用实例」，
> 于是 SSR 下不同请求的状态天然不串——而 Zustand 的模块单例在 SSR 下
> 会把用户 A 的权限泄露给用户 B，需要额外处理。
>
> **本项目不做 SSR（`FNG-2`/`VNG-2`），所以只感受到了 Pinia 的代价、没享受到它的收益。**
> 记这一笔是为了避免得出「Pinia 这里更麻烦」的片面结论。

### 🔴 失误模式

| | 表现 |
| --- | --- |
| React | 无（这个问题不存在） |
| Vue | 白屏 + 报错。**失败得很响，容易修** |

第 14 节会看到一个相反的例子：Zustand 在测试里的隐患**失败得很静**。

---

## 4. 权限判断函数 `usePermission()`

### React

```ts
export function usePermission() {
  const perms = useAuthStore((s) => s.perms)
  // ⚠️ useCallback 不能少：不加的话每次渲染返回新函数，
  //    依赖它的 useMemo 全部失效
  return useCallback(
    (code: PermCode) => perms.includes('*') || perms.includes(code),
    [perms],
  )
}
```

### Vue

```ts
export function usePermission() {
  const auth = useAuthStore()
  // 不需要 useCallback：函数本身不参与依赖追踪，
  // 它读的 auth.perms 才是被追踪的东西
  return { can: (code: PermCode) => auth.can(code) }
}
```

### 差异的实质

React 需要保证**函数引用稳定**（因为引用参与依赖比较）；
Vue 不需要（依赖追踪发生在属性读取那一刻，与函数身份无关）。

> 这是 React 心智负担里很典型的一类：**「值的身份」和「值的内容」都要管。**
> Vue 只管内容。
>
> 代价在别处：Vue 要管「这个值是不是响应式的」（第 2 节的 `storeToRefs`）。
> **两边都有一个额外维度要操心，只是维度不同。**

### 一致的部分（值得注意）

两边都遵守同一条硬规则：**通配 `'*'` 只在这一个函数里处理**。
`<Can>`、路由守卫、菜单渲染全部调它，不重复实现。

这条来自 `F-ADR-009`，**与框架完全无关**——它是「权限规则只能有一处实现」
（后端 `CLAUDE.md` 安全红线第 5 条）在前端的第三次应用。

---

## 5. 按钮级权限：`<Can>` 组件，与 Vue 独有的「指令诱惑」

### React

```tsx
<Can perm={PERM.TICKET_TICKET_DELETE}>
  <Button danger onClick={onDelete}>删除</Button>
</Can>
```

```tsx
export function Can({ perm, fallback = null, children }: CanProps) {
  const can = usePermission()
  const ok = perm ? can(perm) : /* anyOf / allOf */ false
  return <>{ok ? children : fallback}</>
}
```

### Vue

```vue
<Can :perm="PERM.TICKET_TICKET_DELETE">
  <a-button danger @click="onDelete">删除</a-button>
</Can>
```

```vue
<!-- components/Can.vue -->
<script setup lang="ts">
const props = defineProps<{ perm?: PermCode; anyOf?: PermCode[]; allOf?: PermCode[] }>()
const { can } = usePermission()

// ⚠️ 与 React 版逐条对应：什么都不传时**不渲染**（默认拒绝）
const ok = computed(() =>
  props.perm ? can(props.perm)
  : props.anyOf ? props.anyOf.some(can)
  : props.allOf ? props.allOf.every(can)
  : false,
)
</script>

<template>
  <slot v-if="ok" />
  <slot v-else name="fallback" />
</template>
```

| 对应关系 | React | Vue |
| --- | --- | --- |
| 内容 | `children` | 默认 `<slot />` |
| 降级内容 | `fallback` prop | 具名 `<slot name="fallback" />` |
| 类型约束 | `perm?: PermCode` | `defineProps<{ perm?: PermCode }>()` |
| 不传时 | 不渲染 | 不渲染 |

**这一层几乎是同构的。** 差异只是插槽 vs prop。

### 🔴 但 Vue 有第三种写法，而它是个陷阱

```vue
<!-- 几乎所有「Vue 权限管理」教程都会给出这个 -->
<a-button v-perm="PERM.TICKET_TICKET_DELETE" danger>删除</a-button>
```

看起来比 `<Can>` 优雅得多。**本项目明确拒绝它**（[V-ADR-007](02-设计文档.md)），三条理由：

| # | 缺陷 | 实测数据（`vue-v0.7.0`） |
| --- | --- | --- |
| 1 | `mounted` 在元素**挂载之后**执行 | `@vue:mounted` 计数 `{ dir: 1, can: 0 }`——指令版按钮**被创建、被挂载、钩子跑完了**才被删；`<Can>`（`v-if`）根本没创建 |
| 2 | 删掉的元素**不在虚拟 DOM 树上**，`updated` 不再触发 | 运行时 perms 改成 `['*']` 后：指令版 **0 个**（回不来），`<Can>` 版 **1 个**（自动恢复）。🔴 `VE-5.2` 在指令方案下**无法实现** |
| 3 | 模板里的指令值**没有类型检查** | 用 `cs_manager`（有该权限）：正确码 → 1 个，拼错 → **0 个**，而 `vue-tsc` **完全通过** |

📌 **缺陷 3 比预想的更严重。** 初稿写的原因是「指令值的类型是 `any`」，
实测发现即使显式声明 `Directive<HTMLElement, PermCode>`，
`vue-tsc` **依然放过拼错的字符串字面量**——它不校验模板里的指令值。
**这不是「没写类型」，是这条路上没有类型检查。**

📌 **缺陷 2 的暴露时机值得单独记**：它只有在**权限运行时变化**时才看得见，
而那是 `vue-v0.11.0` 的事。**先选了指令方案的话，四个 tag 之后才会发现它是死路。**

第 3 条最讽刺：`F-ADR-012` 说过，

> 「TypeScript 在编译期挡住权限码 typo，**这是 SPA 相比模板版唯一在权限安全性上更强的地方**」

用了指令，**这个唯一的优势就原地退回去了**——退回到 Django 模板
`{% if 'ticket:ticket:delet' in perms %}` 的水平。

### 📌 这一节的结论

> **「Vue 能做而 React 不能做的事」不等于「Vue 应该这么做」。**
>
> 指令是个好机制，但它的三个特性（后置执行、脱离虚拟 DOM、无类型）
> 在权限这个具体场景下**恰好全是负面的**。
>
> 换个场景就不一样了：`v-focus`、`v-resize`、`v-click-outside` 用指令都很合适——
> 它们不参与条件渲染、不需要类型收窄、也不需要在状态变化后恢复。

---

## 6. 动态路由注册：重建 vs 增量

### React：重建整个路由表

```tsx
// AppRouter.tsx —— 真实代码
const dynamicRoutes = useMemo(() => buildRoutes(menus), [fingerprint])

return (
  <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/" element={<RequireAuth><AdminLayout /></RequireAuth>}>
      {dynamicRoutes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
      <Route path="*" element={<UnknownPath />} />
    </Route>
  </Routes>
)
```

路由表是**渲染的产物**。`menus` 变了 → 重新渲染 → 新的路由表。

### Vue：往现有 router 里加

```ts
// src/router/dynamic.ts
let registered: Array<() => void> = []

export function registerDynamicRoutes(menus: MenuNode[]) {
  clearDynamicRoutes()
  for (const record of buildRoutes(menus)) {
    registered.push(router.addRoute('layout', record))   // 返回移除函数
  }
}

export function clearDynamicRoutes() {
  registered.forEach((remove) => remove())
  registered = []
}
```

路由表是 router 实例上的**可变状态**。

### 🔴 差异的实质：「重建」自带清理，「增量」需要还债

| | React | Vue |
| --- | --- | --- |
| 心智模型 | 路由表 = `f(menus)` | 路由表 = 累积的可变状态 |
| 登出后旧路由 | **自动消失**（menus 空了，重新渲染） | 🔴 **还在**，必须手动移除 |
| 换账号 | 自动正确 | 🔴 上个账号的路由残留 |
| 需要写清理代码吗 | **不需要** | **必须**（`VE-3.8`） |

### 📌 实测纠正：真正的坑不在「清理」，在「注册」

**第一版把注册写成守卫里的一个步骤，结果登录时根本不触发：**

守卫只在 `status === 'unknown'` 分支注册，而登录时 status 从
`anonymous` **直接跳到** `authenticated` → 路由没注册 →
跳 `/tickets` 匹配不到 → **403**。「登录成功，然后被自己的前端拒之门外」。

| | React | Vue（第一版） |
| --- | --- | --- |
| 路由表是什么 | `f(menus)`，**派生值** | 需要被执行的**动作** |
| menus 变了 | 自动重算 | 得有人记得去调 |
| 「profile 到手」有几个时机 | **不关心** | **两个**，漏一个就出 bug |

**修法不是补第二个调用点，是把它变回派生值：**

```ts
watch(() => auth.menus, (menus) => {
  menus.length === 0 ? clearDynamicRoutes() : registerDynamicRoutes(router, menus)
}, { flush: 'sync' })      // ⚠️ 'pre' 赶不上守卫紧接着的重新导航
```

**副产品：清理变免费了。** `auth.reset()` 清空 menus → watcher 移除路由，
登出清单又回到和 React 一样的四项。

> **「增量 API 多欠一笔债」是真的，但债可以一次性还清**：
> 把命令式的 `addRoute` 包装成派生效果，就拿回了 React 的那个性质。
> **代价是你必须自己想到这一步——框架不会提示你。**

### ⚠️ 而且我原先预言的后果**没有发生**

本节初稿（以及 `VE-3.8`、`V-ADR-004`）写着：

> 换个权限更小的账号 → 路由还在 → **进得去但一片空白** → 用户以为系统坏了

**关掉全部清理逻辑后实测**：

| 现象 | 结果 |
| --- | --- |
| 登出后 `/system/users` 还在路由表吗 | ✅ **在**（残留是真的） |
| `cs_staff` 登录后 `/tickets` | ⚠️ 注册了**两次** |
| `push('/system/users')` | **403**，不是空白页 |

因为守卫**每次导航**都查 `to.meta.perm`，残留路由带的是**上一个用户的** permCode。
那个预言隐含假设「守卫只在注册时判断一次」——实际不是。
React 版有同样的第二道（`<PermissionGate perm={node.permCode}>`）。

清理仍要做，但理由换成真的：**重复注册无限增长**、
**路由表泄露上个用户能进哪些页面**、**同 path 映射到不同 component 时行为不确定**。

> 📌 **「这个 bug 会造成什么后果」和「这个 bug 存在」是两件事。**
> 我把前者写死在文档里，而它依赖另一层的行为——那一层恰好也做了防护。
> 这类「靠另一层兜住」的推断，不实测就永远不知道对不对。

### 为什么用 `addRoute` 的返回值而不是 `removeRoute(name)`

`removeRoute(name)` 要求每条路由有唯一 `name`。菜单是后端下发的，
`name` 由 `route_path` 派生——**两个菜单指向同一组件时会撞名**，
而撞名的表现是「移除了不该移除的那条」，极难排查。
`addRoute` 的返回值不依赖 name，是精确的。

### 📌 这一节的结论

> **「增量 API」比「重建 API」多欠一笔债，而这笔债不会主动来找你。**
>
> 它只在「第二次」才暴露：第二次登录、第二个账号、第二次权限变更。
> 而开发时你几乎总是在测「第一次」。
>
> `vue-v0.5.0` 的规格书**要求先写出有 bug 的版本并亲眼看到它**，
> 就是因为这个 bug 在 React 版根本不会出现，不主动制造就永远遇不到。

---

## 7. 路由守卫：渲染期 vs 导航期

### React：守卫是组件树里的一个节点

```tsx
// router/PermissionGate.tsx —— 真实代码
export function PermissionGate({ perm, children }: { perm: PermCode | null; children: ReactNode }) {
  const can = usePermission()
  if (perm && !can(perm)) return <Navigate to="/403" replace />
  return <>{children}</>
}
```

它在**渲染时**判断。React Router 已经匹配完路由、开始渲染这棵子树了，
`PermissionGate` 在渲染过程中把它换成一个重定向。

### Vue：守卫是导航流程的一个环节

```ts
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.perm && !auth.can(to.meta.perm as PermCode)) return { path: '/403' }
  return true
})
```

它在**导航前**判断。**页面组件根本不会被创建。**

### 差异的实质

| | React（渲染期） | Vue（导航期） |
| --- | --- | --- |
| 页面组件 | **已创建**，然后被替换 | **不创建** |
| 页面里的 `useQuery` | ⚠️ 可能已经发出请求 | 不会发出 |
| URL | 先变，再渲染 403 | 可在变之前重定向 |
| 表达形式 | JSX 节点 | 函数返回值 |
| 能否 `await` | 不能（渲染必须同步） | **能**（第 8 节靠这个） |

「能不能 `await`」是个大差异：Vue 的守卫可以在导航过程中等一个网络请求完成，
React 的渲染函数不行，只能靠「先渲染 loading，请求完了再渲染内容」。

### 🔴 但这不是「Vue 的守卫更安全」

**这是本文档最需要强调的一处认知风险。**

Vue 的守卫拦得更早、更彻底，写出来也更像鉴权：

```ts
if (!can(to.meta.perm)) return '/403'      // 看起来就是在做鉴权
```

**它挡不住任何攻击者。** `can()` 读的是浏览器内存里的 Pinia store：

```js
// Vue Devtools 里点两下，或者控制台一行
$pinia.state.value.auth.perms = ['*']
```

而且攻击者根本不导航——他直接 `curl`。**守卫这一层对他完全不存在。**

> `frontend/CLAUDE.md` 里那句话在 Vue 版更适用：
>
> > **路由守卫比隐藏按钮更容易造成错觉，因为它写起来太像鉴权了。**
>
> Vue 的导航期守卫**写起来更像**，所以**错觉更强**。

它真正省下的是**用户这边**的开销（不创建组件、不发无用请求），
这是**体验优化**，与安全无关。

### 🔴📌 导航期守卫的代价：它对「状态变化」完全无感（`vue-v0.2.0` 实测）

**这一条原本不在计划里，是写登出时被真 bug 逼出来的。**

```
登出 → session 清了、store 清了、cookie 也没了
     → 但用户**仍然停在原页面上**，界面还是登录态的壳
```

| | React | Vue |
| --- | --- | --- |
| 守卫是什么 | **组件**，在渲染树里 | **导航流程的一环** |
| `status` 变 `anonymous` 时 | 重新渲染 → `<Navigate>` **自动生效** | **没有导航发生 → 守卫根本不会运行** |
| 要写跳转代码吗 | ❌ 不需要 | ✅ **必须** |

```ts
// React：什么都不用做。RequireAuth 是组件，status 一变它自己就重定向了
queryClient.clear(); reset()

// Vue：必须显式导航，否则用户停在原地
queryClient.clear(); auth.reset()
await router.replace('/login')      // 🔴 少了这行就是 bug
```

**根因是一句话**：

> **React 的守卫是「状态的函数」，Vue 的守卫是「导航的钩子」。**
> 前者对状态变化天然响应，后者只在有人导航时才醒来。

→ 硬规则：**凡是「状态变了所以该换页面」的场景，Vue 都必须自己发起导航。**
本项目目前有两处：`useLogout` 的 `onSettled`、`api/client.ts` 的 401 回调。

⚠️ 这顺带解释了一件之前没想通的事：401 为什么必须**注入一个跳转回调**
而不能只在拦截器里清 store——**同一个原因**。

### 🔴📌 同一类差异的第二面：「注入」发生的时机（`vue-v0.3.0` 实测）

`vue-v0.2.0` 埋了一个 bug，`vue-v0.3.0` 才炸出来：

```
直接打开 /login → 引导阶段拉 profile 拿到 401
  → 401 handler 把 URL 改成 /login?redirect=/login
  → 登录成功 → target = '/login' → **跳回登录页**
```

**React 版的这段逻辑逐字相同，`safeRedirect` 也一样不拦 `/login`——
实测跑起来它却不出问题。** 原因在组件树的形状：

```tsx
<AuthBootstrap>            {/* status==='unknown' 时只渲染 spinner，不渲染 children */}
  <UnauthenticatedBridge />     {/* setUnauthenticatedHandler 在它的 useEffect 里 */}
</AuthBootstrap>
```

引导阶段那个 401 到达时，**处理器根本还没装上**。

| | React | Vue |
| --- | --- | --- |
| 「注入」发生在 | **组件挂载**（`useEffect`） | **setup**（同步，立即） |
| 引导阶段的 401 | 处理器未装 → **无害** | 已装 → **立刻跳转** |
| 保护来自 | 组件树层级 | 必须**显式**写判断 |

> **React 的行为由组件树的形状决定，Vue 的行为由代码的执行顺序决定。**

这句话把本节两个发现串起来了：

| 现象 | 同一个根因 |
| --- | --- |
| 登出后不跳转 | React 的守卫**在树里**，状态一变就重渲染；Vue 的在导航流程里，不导航就不醒 |
| 引导期 401 写坏 redirect | React 的注入**在树里**，父节点不渲染它就不生效；Vue 的在 setup 里，无条件生效 |

⚠️ 但别把 React 那一侧读成「更好」——它那道保护是**顺带得来的**：
`AuthBootstrap.tsx` 的注释讲的是「防死锁」，**完全没提这件事**。

> **一个没被写下来的保护，重构时最容易被弄没。**
> Vue 被迫把它写成一行显式判断，反而更耐改。

### 📌 一个反直觉的结论

| | 拦截时机 | 状态变化时自动响应 | 安全价值 |
| --- | --- | --- | --- |
| React 渲染期守卫 | 晚 | ✅ | **0** |
| Vue 导航期守卫 | 早 | ❌ | **0** |
| 后端 `HasPerm` | 最晚（请求到达服务器） | — | **全部** |

**拦得早不等于拦得住。** 唯一决定安全的是「拦在哪一侧」，不是「拦在哪一步」。

而中间那一列说明：**「拦得早」和「响应状态变化」是一对取舍，不是免费的升级。**
`01-PRD.md` 第 1.3 节预判「Vue 拦得更早，但错觉也更强」——
**错觉那一半说对了，这个代价没想到。**

---

## 8. 刷新页面变 404：同一个陷阱，两种解法

**这是两边都会遇到的经典时序问题**（`FE-3.7` / `VE-3.7`）：

```
用户在 /tickets/42 按 F5
    → 应用启动，路由表是空的（menus 还在路上）
    → 匹配不到 /tickets/42
    → 404
```

### React：控制**渲染**时机

```tsx
// AuthBootstrap.tsx —— 真实代码
if (status === 'unknown') return <FullPageSpin tip="正在加载权限信息" />
return <>{children}</>       // profile 到手才渲染 AppRouter
```

**profile 没到，`<RouterProvider>` 就不存在**，也就不会有「匹配不到」这回事。

⚠️ React 版在这里踩过一个坑，`AuthBootstrap.tsx` 的注释记着：

> 第一版我把它放进了受保护区内部，结果是**死锁**——
> `RequireAuth` 看到 `status === 'unknown'` 就只渲染 spinner，
> 于是 `AuthBootstrap` 永远不挂载，profile 永远不发请求，status 永远是 unknown。
>
> **「谁负责触发认证状态的确定」必须在「谁依赖这个状态」之上。**

### Vue：控制**导航**时机

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

    // 🔴 关键的一行
    return { ...to, replace: true }
  }
  ...
})
```

### 🔴 `return { ...to, replace: true }` ——「导航到我自己刚才要去的地方」

这行代码看起来像死循环，是 Vue 版**最不直观**的一处。

**为什么必须有它**：`addRoute()` 之后，参数 `to` 是**在旧路由表上算出来的**
（大概率已经落到 404 兜底路由）。直接 `return true` 会渲染那个 404。
必须重新发起导航，让它在**新**路由表上重新匹配。

**为什么它不是死循环**：第二次进守卫时 `auth.status` 已经不是 `'unknown'`，
不会再进这个分支。

> ⚠️ **这个保证藏在另一个变量里，是整段代码最脆弱的地方。**
>
> 如果 `fetchProfileIntoStore()` 失败时**没有**把 `status` 置成终态，
> 守卫会无限重定向，Vue Router 抛 `Maximum recursive navigation guard calls`。
>
> → 硬规则：`fetchProfileIntoStore()` **无论成功失败都必须把 status 置为终态**
> （`'authenticated'` 或 `'anonymous'`）。这条写进 `vue-v0.4.0` 的验收清单。

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 解法 | 不渲染 | 不放行 + **重新导航一次** |
| 直观度 | 较好（「没准备好就别渲染」） | 🔴 差（返回值看起来像死循环） |
| 失败模式 | **死锁**（永远转圈） | **无限重定向**（抛异常） |
| 保证正确的前提 | 组件层级正确 | `status` 一定会到终态 |
| 前提被破坏时 | 静默转圈，很难查 | **抛异常**，报错明确 |

> 又一次：**Vue 失败得更响，React 失败得更静。**
> 这个模式在第 3 节、第 14 节还会出现——它似乎不是巧合，
> 而是「显式声明 vs 隐式推导」这条设计路线的一贯后果。

---

## 9. 服务端状态：TanStack Query 的两个适配层

这是**唯一一个「同一个库的两个适配层」**的对照，条件近乎理想：
`@tanstack/react-query` 和 `@tanstack/vue-query` **版本号都是 5.101.4**，
同一套缓存语义、同一套失效逻辑，**只有响应式接入方式不同**。

### React

```tsx
const [params, setParams] = useTableQuery(DEFAULTS)

const { data, isLoading } = useQuery({
  queryKey: ['tickets', params],      // 每次渲染重新求值 → 天然响应
  queryFn: () => fetchTickets(params),
})

return <Table dataSource={data?.results} loading={isLoading} />
```

### Vue

```vue
<script setup lang="ts">
const { params } = useTableQuery(DEFAULTS)

const { data, isLoading } = useQuery({
  // 🔴 必须是 computed
  queryKey: computed(() => ['tickets', params.page, params.status]),
  queryFn: () => fetchTickets(params),
})
</script>

<template>
  <!-- 模板里自动 unref，不写 .value -->
  <a-table :data-source="data?.results" :loading="isLoading" />
</template>
```

### 🔴 最容易踩且**完全不报错**的一个坑（`vue-v0.8.0` 实测）

```ts
// ❌ 改了筛选条件，列表**不会**重新请求
queryKey: ['tickets', params.value]
```

数组字面量在 `<script setup>` 里**只求值一次**。`queryKey` 定死了，
`params` 后续怎么变都不会触发重新请求。

**📌 实测数据**（故意写成上面这行，跑一遍）：

| 检查项 | 结果 |
| --- | --- |
| `vue-tsc` 类型检查 | ✅ **完全通过，退出码 0** |
| 首次加载 | ✅ **对的**（20 行） |
| 改筛选后 URL | ✅ 变了（`?status=closed`） |
| 改筛选后表格 | ❌ **纹丝不动，还是 20 行**（应为 0） |
| 控制台报错/警告 | **一条都没有** |

⚠️ 四项里三项看起来都是对的——**这就是它难查的原因**。
你会先去怀疑后端筛选、怀疑 URL 同步、怀疑分页组件，
最后才想到「请求根本没发出去」。

React 侧这个 bug **不可能存在**——组件函数每次重新执行，`queryKey` 每次重新求值。

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 返回值 | 普通值 | `Ref`（script 里 `.value`，模板里自动 unref） |
| `queryKey` 响应性 | 重渲染天然提供 | **必须显式 `computed`** |
| 写错的表现 | — | **静默失效** |
| `enabled` 等选项 | 值 | 也可以是 `computed` |

### 📌 本项目的对策（[V-ADR-009](02-设计文档.md)）

**所有带参数的 `useQuery`，`queryKey` 一律写成 `computed(() => [...])`，
即使当前没有参数会变。**

理由：「现在没参数」会变成「以后加了参数」，而加参数的人不会想到还要改
`queryKey` 的形式。统一写法把陷阱从「需要记住」变成「不可能踩到」。

> 这与 React 版的一条经验同源。`useProfileQuery.ts` 里记着：
>
> > TanStack Query v5 **移除了 `useQuery` 的 `onSuccess`**……
> > 而且它**不报错，是静默失效**。
>
> **同一个库，在两个框架里各留了一个静默失效点。**
> 这大概说明：跨框架的抽象层最容易在「响应式接缝处」出问题——
> 因为那正好是它必须适配、又无法统一的地方。

---

## 10. 分页与筛选同步到 URL

两边的**理由完全相同**（`fe-v0.10.0` 的注释）：

> 分页和筛选确实是「客户端状态」，但它属于**地址**而不是**组件**：
> 刷新后条件还在、链接可以分享。用 `useState` 两条都做不到。

### React

```ts
const [searchParams, setSearchParams] = useSearchParams()

const params = useMemo(() => { /* 从 searchParams 还原类型 */ }, [searchParams, defaults])

const setParams = useCallback((patch: Partial<T>) => {
  const next = new URLSearchParams(searchParams)
  ...
  setSearchParams(next, { replace: true })
}, [searchParams, setSearchParams])
```

### Vue

```ts
export function useTableQuery<T extends Record<string, string | number>>(defaults: T) {
  const route = useRoute()
  const router = useRouter()

  // route.query 本身就是响应式的，不需要订阅
  const params = computed(() => { /* 从 route.query 还原类型 */ })

  function setParams(patch: Partial<T>) {
    router.replace({ query: { ...route.query, ...cleaned(patch) } })
  }

  return { params, setParams }
}
```

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 读 URL | `useSearchParams()` 返回值 | `useRoute().query`（**天生响应式**） |
| 写 URL | `setSearchParams(next, { replace })` | `router.replace({ query })` |
| 稳定引用 | 需要 `useMemo` + `useCallback` | 不需要 |
| 代码量 | ~30 行 | ~20 行 |

**这一节 Vue 明显更短**，因为「URL 是响应式数据源」这件事在 Vue Router 里是内建的，
不需要额外的订阅层。

⚠️ 但**两边都必须记得 `replace: true`**——不加的话改一次筛选就在历史里堆一条，
用户按返回键要点十几次才能离开页面。**这个坑与框架无关。**

---

## 11. 把 Query 的结果写进 store：一个跨框架的时序陷阱

### React：踩过的坑（`fe-v0.13.0`）

```ts
// useProfileQuery.ts —— 真实代码
useEffect(() => {
  if (query.data) setProfile(query.data)
  else if (query.isError) reset()
}, [query.data, query.isError, setProfile, reset])
```

`versionWatcher.ts` 的注释完整记录了那个 bug：

> ⚠️ `refetchProfile` 必须**返回拉到的新 profile**，不能只返回 void 让调用方回头去读 store。
>
> 原因是时序：store 的写入走的是 `useProfileQuery` 里的 `useEffect`，
> 而 `useEffect` 要等 React 重新渲染才跑。
> **`await refetchQueries()` 解决的那一刻，store 里还是旧值。**
>
> 我第一版就是读 store 比对的，结果是：按钮确实消失了（React 后来渲染了），
> 但**提示永远不弹**（比对时新旧一样）。
> 这个 bug 只在 E2E 里能发现——**单测里 mock 的 refetch 是同步改 store 的**。
>
> 规则：**「异步操作完成」和「派生状态已更新」是两件事。**

### Vue：同一个位置，换成 `watch`

```ts
const { data } = useQuery({ queryKey: ['profile'], queryFn: fetchProfile, ... })

watch(data, (profile) => {
  if (profile) auth.setProfile(profile)
}, { immediate: true })
```

### 📌 这个陷阱在 Vue 里还在吗？

**待实测，`vue-v0.11.0` 给答案并回填本节。**

已知的分析：

| | React `useEffect` | Vue `watch`（默认 `flush: 'pre'`） |
| --- | --- | --- |
| 触发时机 | 渲染**提交后** | 组件更新**前**（同一个 tick 内） |
| `await refetch()` 之后 | ❌ 尚未执行 | ⚠️ **可能已执行，也可能没有** |

`watch` 的回调在 Vue 的调度队列里，`await` 一个网络请求之后**微任务队列已经刷过一轮**，
所以**很可能**已经跑了。但这依赖调度细节，**不能靠**。

**无论实测结果如何，本项目都保留 React 版的解法**：

```ts
// ✅ 直接用返回值，不绕道读 store
const fresh = await refetchProfile()
if (!sameSet(before, fresh.perms)) notify('你的权限已更新')
```

理由：那条规则（**「异步操作完成」≠「派生状态已更新」**）是对的，
即使某个框架的某个版本恰好让你侥幸过关。

> ⚠️ **这一节还藏着一个更重要的教训，而它与框架无关：**
>
> > 单测里 mock 的 `refetch` 是**同步**改 store 的，所以单测**永远是绿的**。
>
> 一个把异步简化成同步的 mock，会让所有依赖真实时序的 bug 隐形。
> 这条在 Vue 版**同样成立**，`vue-v0.13.0` 会重复这个教训。

---

## 12. 错误边界：React 唯一的 class vs Vue 的两个钩子

### React

```tsx
// ⚠️ 必须仍然是 class 组件。React 到今天也没有 hook 版的 Error Boundary，
//    这是极少数 hook 覆盖不到的场景。
export class AppErrorBoundary extends Component<Props, State> {
  static getDerivedStateFromError(error: Error): State { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(...) }
  render() {
    if (this.state.error) return this.props.fallback(() => this.setState({ error: null }))
    return this.props.children
  }
}
```

### Vue

```vue
<script setup lang="ts">
const error = ref<Error | null>(null)
onErrorCaptured((err) => {
  error.value = err as Error
  return false      // ⚠️ 阻止继续向上冒泡，否则全局 handler 会重复处理同一个错误
})
</script>

<template>
  <ErrorResult v-if="error" :error="error" @retry="error = null" />
  <slot v-else />
</template>
```

外加一层全局兜底：

```ts
app.config.errorHandler = (err, instance, info) => { /* 上报 */ }
```

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 机制 | class 生命周期 | composition 钩子 |
| 全局兜底 | 无内建（要自己在根部包一层） | `app.config.errorHandler` |
| 冒泡控制 | 边界捕获即停止 | `return false` 显式停止 |
| 写法 | 🔴 **必须写 class** | 与其他逻辑一致 |

### 🟢 但**限制完全相同**，这才是重点

两边**都不捕获**：

- 事件处理器里的错误（`onClick` / `@click` 里 throw）
- `setTimeout` / Promise 回调里的错误
- 异步 `queryFn` 的 reject

所以在两个前端里，**5xx 都不能靠错误边界兜住**——
API 错误走 axios 拦截器那条路，错误边界管的是**渲染崩溃**。

> **这个限制不是框架的选择，是「同步渲染栈之外的错误无法被组件捕获」这个事实。**
> 换框架改变不了它。凡是这类「两边完全一样」的限制，都值得特别标注——
> 它们是真正的约束，而不是可以通过选型绕开的东西。

⚠️ Vue 独有的一个小坑：忘了 `return false`，错误会被处理两次
（局部降级 + 全局上报同一个错）。→ 单测里断言全局 handler 没被调用。

---

## 13. 表单：受控组件 vs `v-model`

### React

```tsx
const [form] = Form.useForm()

<Form form={form} onFinish={onSubmit}>
  <Form.Item name="title" label="标题" rules={[{ required: true }]}>
    <Input />
  </Form.Item>
</Form>
```

### Vue

```vue
<a-form :model="formState" @finish="onSubmit">
  <a-form-item name="title" label="标题" :rules="[{ required: true }]">
    <a-input v-model:value="formState.title" />
  </a-form-item>
</a-form>
```

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 数据流 | 单向 + 回调（antd 的 `Form` 内部代管） | `v-model` 双向 |
| 取值 | `form.getFieldsValue()` | 直接读 `formState` |
| 服务端字段错误回填 | `form.setFields([...])` | `formRef.value.validate` / 手动映射 |

**权限相关的部分完全一样**：

```
❌ 表单用 exclude 黑名单                 ← 后端红线 3，与前端无关
❌ is_superuser 出现在任何 Web 表单      ← 后端红线 4，与前端无关
✅ 按权限禁用字段（体验），后端必须有对应校验（安全）
```

这两条红线**不因框架变化**——它们讲的是「哪些字段可以被提交」，
而那由后端序列化器决定，前端写什么都改变不了。

⚠️ `utils/formErrors.ts`（把后端的 `{field: [msg]}` 映射到表单）两边**逻辑相同**，
只是最后一步的调用 API 不同。这属于「同构改写」。

---

## 14. 测试：两种相反的隔离麻烦

### 单测：store 隔离

```ts
// React：Zustand 是模块级单例 → 测试之间会串 → 必须手动 reset
beforeEach(() => useAuthStore.setState(INITIAL))

// Vue：Pinia 需要 active 实例 → 必须手动创建
beforeEach(() => setActivePinia(createPinia()))
```

**两个都不能忘，但忘了的表现相反**：

| | 忘了会怎样 | 难查程度 |
| --- | --- | --- |
| React | 测试**顺序相关**：单跑绿、全跑红、换个顺序又绿 | 🔴 极难 |
| Vue | **立即抛错**，报错直接说明原因 | 🟢 容易 |

> 第三次出现同一个模式（第 3 节、第 8 节、这里）：
> **Vue 失败得更响，React 失败得更静。**
>
> 这不是「Vue 更好」——「失败得响」的代价是你必须在更多地方写显式声明。
> 但在**测试**这个场景里，失败得响确实是纯收益：
> 顺序相关的测试是所有测试问题里最消耗时间的一类。

### 断言时序

```ts
// React：状态更新是异步批处理的，需要轮询等待
await waitFor(() => expect(screen.getByText('删除')).toBeInTheDocument())

// Vue：DOM 更新在 nextTick，时序确定
store.perms = ['ticket:ticket:delete']
await nextTick()
expect(screen.getByText('删除')).toBeInTheDocument()
```

⚠️ **Vue 的确定性有个上限**：如果链路里是「`watch` 触发 `watch`」，
一个 `nextTick` 不够，表现是「断言偶尔失败」。
→ 遇到就用 `await flushPromises()`，**不要靠加 `nextTick` 凑数**——
凑出来的数字下次改代码就不对了。

### 🟢 完全没差异的部分

| 项 | 说明 |
| --- | --- |
| **MSW handlers** | 🟢 **逐字复用**。它拦的是网络层，与框架无关 |
| **不 mock axios** | 🟢 同一条规则：「我们有一半权限逻辑在拦截器里，mock 掉 axios 它们一行都不会执行」 |
| **结构性测试** | 🟢 扫源码对账 `<Can>` 与后端 `@require_perm`，只改文件后缀 |
| **`no-client-side-filtering`** | 🟢 逐字复用（`F-ADR-015` 与框架无关） |
| **「断言被拒绝时必须证明换个身份就不被拒」** | 🟢 同一条铁律 |

---

## 15. E2E：一个字都不用改

### 复用的部分

`frontend-vue/e2e/` 从 `frontend/e2e/` 复制，**只改三处**：

| 改什么 | 为什么 |
| --- | --- |
| `baseURL: 5173 → 5174` | 端口 |
| `bypass.spec.ts` 的篡改方式 | 见下 |
| 极少数 DOM 类名 | antd 6 与 antdv 4 是不同版本世代 |

**其余全部逐字相同，包括所有断言值。**

```ts
// matrix.spec.ts —— 两个前端**完全相同**
const SCOPE_MATRIX: Array<[string, number]> = [
  ['superadmin', 80], ['sysadmin', 80], ['cs_manager', 50], ['cs_staff', 5],
]
```

### 🎯 唯一的实质差异：篡改 store 的方式

**React 需要专门开一个口子**：

```ts
// auth/store.ts —— 只在 e2e 构建里挂
if (import.meta.env.VITE_EXPOSE_AUTH_STORE === '1') {
  window.__AUTH_STORE__ = useAuthStore
}
```

```ts
// bypass.spec.ts
await page.evaluate(() => window.__AUTH_STORE__.setState({ perms: ['*'] }))
```

**Vue 不需要**——Pinia 的 state 本来就挂在 app 上，是个可写的响应式对象：

```ts
await page.evaluate(() => {
  const pinia = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia
  pinia.state.value.auth.perms = ['*']
})
```

而且**改完立刻生效，不需要触发任何重渲染**（响应式自动传播）。

### 📌 这个差异说明了什么

> React 版为了**演示**「前端权限可以被篡改」，专门加了一个 e2e-only 的全局变量，
> 还在注释里花了一整段解释「这不是为了测试而降低安全」。
>
> **Vue 版连这段解释都不需要**——store 本来就是公开可写的。
>
> 这不是 Vue 的安全缺陷。**两边的实际暴露程度完全一样**：
> React DevTools 同样能改任何组件状态，攻击者同样可以完全不用你的前端。
>
> Vue 只是**把「前端状态从来就不是秘密」这件事表达得更诚实**，
> 让那段解释变得多余。

### 🎯 断言逐格不变，是验收项而不是省事

`VAC-8` 把「断言值与 React 版逐字相同」列为**验收条件**。

> **一份能跨框架复用的 E2E，才是真正的规格说明书。**
>
> 如果换个框架就有大量断言要跟着改，那说明它测的是**实现**，不是**规格**。
>
> 越权矩阵在四种表现层（模板 / DRF / React / Vue）下**逐格相同**——
> 这证明它描述的是**系统的权限行为**，而权限行为不该因为前端换了框架而改变。

---

## 16. UI 库的接入方式：全局注册 vs 按需 import

> 📌 **本节是 `vue-v0.1.0` 实测出来的，原本不在计划里。**
> 它是本阶段第一个「不是我预判的」差异。

### React：只有一种写法

```tsx
import { Button, Card, Alert } from 'antd'
```

React 没有「全局组件」这个概念——组件就是变量，要用必须 import。
**于是 tree-shaking 天然生效**，你根本没有写错的机会。

### Vue：有两种写法，而**默认推荐的那种是错的**

```ts
// ❌ 几乎所有 Vue + Ant Design Vue 教程的第一行
import Antd from 'ant-design-vue'
app.use(Antd)          // 全局注册**所有**组件
```

```vue
<!-- 好处：模板里直接写短横线标签，不用 import -->
<a-button type="primary">提交</a-button>
```

**代价是 tree-shaking 完全失效。** `vue-v0.1.0` 的实测数据：

| | 内容 | `dist/assets` 合计 |
| --- | --- | --- |
| React（`fe-v1.0.0`） | **12 个页面、全部功能** | **1.24 MB** |
| Vue（`app.use(Antd)`） | **一个占位页** | **1.53 MB** |
| Vue（按需 import） | 一个占位页 | **0.51 MB** |

**一个占位页比人家整个应用还大。**

### 正确写法

```vue
<script setup lang="ts">
import { Alert, Button, Card } from 'ant-design-vue'
</script>

<template>
  <Button type="primary">提交</Button>
</template>
```

`<script setup>` 里 import 进来的组件在模板里直接可用，不需要 `components` 选项。
**这一点和 React 的 `import { Button } from 'antd'` 完全同构。**

⚠️ 代价是模板里写 `<Button>` 而不是 `<a-button>`——啰嗦一点，也不那么「Vue 味」。

### 差异的实质

| | React | Vue |
| --- | --- | --- |
| 组件的存在方式 | **变量**（必须 import） | 变量 **或** 全局注册 |
| 默认路径 | 只有一条，且是对的 | 两条，**教程推荐的那条有体积陷阱** |
| 写错的表现 | 不可能写错 | **构建成功、运行正常、包大三倍** |
| 什么时候发现 | — | 上线前看 bundle report，或者永远不发现 |

### 📌 为什么本项目必须选按需 import

不是因为「体积重要」（教学项目不在乎），而是 [V-ADR-002](02-设计文档.md)：

> **凡是与框架无关的，用完全相同的库和版本。** 控制变量。

React 版用的是按需 import。如果 Vue 版用全局注册，那么 `vue-v1.0.0` 收口时
量出来的体积差异**是「注册方式的差异」，不是「框架的差异」**——
一个被自己的实验设计污染的结论。

### 🔴 这个陷阱的类型很值得注意

它和第 9 节的 `queryKey`、第 6 节的动态路由清理是**同一类**：

> **框架给了你两条路，其中一条更省事、更「地道」、文档里排在前面，
> 而它在某个维度上是错的——且不报错。**

三个例子的共同点是**「默认路径不是正确路径」**。
React 在这三处都只给了一条路（重渲染天然响应、重建 router 天然清理、
组件必须 import），**所以你没有机会走错**。

这是「灵活性」的真实成本：**每一条额外的路，都是一个需要被文档化的选择。**
本项目为它写了三条 V-ADR（004 / 009 + 本节），而 React 版一条都不需要。

### 📌 附：「照抄 React 版会写出无效属性」实测清单

这是同一个模式在 UI 库层面的表现，实施过程中已经遇到 4 次：

| tag | 位置 | React（antd 6） | Vue（antdv 4） | 类型 |
| --- | --- | --- | --- | --- |
| `vue-v0.2.0` | `ConfigProvider` | `button={{ autoInsertSpace: false }}` | `:auto-insert-space-in-button="false"` | 换了名字 |
| `vue-v0.2.0` | `Spin` | `description` | `tip` | 换了名字（**方向相反**：antd 6 弃用了 `tip`） |
| `vue-v0.3.0` | `Menu` | `defaultOpenKeys` | **不存在**，只有受控的 `openKeys` | **能力不存在** |
| `vue-v0.10.0` | `Modal` | `destroyOnHidden` | `destroyOnClose` | 换了名字 |
| `vue-v0.9.0` | `Modal.confirm()` | 需要 `<App>` + `App.useApp()` | **同样需要** | 🟢 **不是差异——是我漏抄了** |

📌 最后一行是个反例，值得单独说：静态的 `Modal.confirm()` 在组件树**之外**
渲染，拿不到 `<ConfigProvider>` 配置，按钮实测渲染成 **「确 定」**。
**React 版早就用 `<App>` + `App.useApp()` 解决了**（antd 5 引入 `<App>` 正是为此），
我照抄时漏掉了——因为那个解法在 `main.tsx` 的一层组件包装里，
不在我当时正在抄的那个文件里。

> **「照着另一个实现写」比「从零写」少踩很多坑，
> 但它会漏掉那些「不在你视线范围内的文件」里的决策。**

⚠️ **这是 UI 库版本世代的差异，不是 Vue/React 的差异**——
antdv 4 对应的是 antd **5** 的 API 世代，不存在「antd 6 的 Vue 版」。
**必须诚实记录，不能假装是「Vue 的问题」。**

### 🔴📌 而有一处是**两边一样坏**：`defaultExpandAllRows`

`vue-v0.10.0` 实测，树形表格只显示顶层节点：

| 页面 | 实际 | 应该 |
| --- | --- | --- |
| 权限点 | **4 行** | 26 行 |
| 部门 | **1 行** | 6 行 |

原因是它只在首次渲染时算一次默认展开项，而那时数据（来自 `useQuery`）还没到。

**把 React 版跑起来验证：一模一样，也是 4 行和 1 行。**

所以这不是框架差异，是 antd/antdv 共有的行为。
而 `fe-v0.12.0` 的 92 个 E2E **从没断言过行数**，所以它至今还在 React 版里。
Vue 阶段发现它，只因为我写了一条 `permRows === 26`。

> 📌 **这是本阶段第 3 次出现同一个模式：**
> **接下一个前端时挖出的问题，绝大多数不在「新框架怎么写」，
> 而在「上一个实现里没人验证过的地方」。**
>
> 前两次（派单下拉框泄露全部用户、数据范围无审计）是 React 阶段自己发现的；
> 这一次是 Vue 阶段发现的、**React 阶段至今仍存在的**。
>
> ⚠️ 本项目只修了 Vue 版——`frontend/` 要保持 `fe-v1.0.0` 原样以供对比。
> 那个 bug 留在原处，是这条结论的活证据。

但**它们为什么全都静默失效**，就是框架层面的差异了：

> **Vue 的模板对未知属性是宽容的**（透传到 `$attrs` 落在根元素上），
> 而 React 的 TSX 对未知 prop **编译期报错**。

这是 JSX 相对模板在这一点上实打实的优势。
⚠️ 反面也要看到：正因为宽容，Vue 的模板才能把任意属性透传给子组件，
封装第三方组件时省掉大量样板。**同一个特性，两个方向的后果。**

---

## 17. 总账：哪些与框架无关？

### 17.1 按层统计

| 层 | 与框架的关系 | 复用程度 |
| --- | --- | --- |
| 后端权限内核 | 完全无关 | 🟢 **0 行改动**（第四次） |
| 后端适配层 | 完全无关 | 🟢 **≈20 行**（两个管理命令加 `--out`） |
| axios 拦截器 / CSRF / 错误分流 | 完全无关 | 🟢 几乎逐字 |
| MSW handlers / 测试夹具 | 完全无关 | 🟢 逐字 |
| E2E 越权矩阵 | 完全无关 | 🟢 逐字（三处例外） |
| 菜单树适配逻辑 | 无关 | 🟢 逻辑逐字，渲染不同 |
| 权限判断函数 | 基本无关 | 🟡 同构改写 |
| `<Can>` 组件 | 基本无关 | 🟡 同构改写 |
| 表单 / 表格页面 | 中等相关 | 🟡 同构改写 |
| **状态实例化与订阅** | 🔴 **强相关** | 🔴 重新设计 |
| **动态路由注册** | 🔴 **强相关** | 🔴 重新设计 |
| **路由守卫的位置** | 🔴 **强相关** | 🔴 重新设计 |

### 17.2 决策统计

15 条 V-ADR 里：

| 类别 | 数量 | 是哪些 |
| --- | --- | --- |
| 🟢 直接继承 | **4** | 006 三态、012 E2E 复用、014 产物不入库、015 不做二次过滤 |
| 🟡 微调 | **2** | 008 导出命令加 `--out`、002 选型对齐 |
| 🔴 重新决策 | **9** | 001 / 003 / 004 / 005 / 007 / 009 / 010 / 011 / 013 |
| 其中真正 **Vue 特有** | **6** | 003 store 时序、004 路由清理、007 指令、009 queryKey、011 测试隔离、013 文件式路由 |

**那 6 条全部集中在两个点上**：

```
① 状态的实例化与响应式边界   → V-ADR-003 / 009 / 011
② 路由表的注册方式           → V-ADR-004 / 005 / 013
```

> 换框架真正要重新想的，就这两件事。
> **其余全都是同构改写或直接复制。**

### 17.3 两个 tag 直接消失了

| React tag | Vue 阶段工作量 |
| --- | --- |
| `fe-v0.2.0` 后端 Session + CSRF | **0** |
| `fe-v0.5.0` 后端路由字段 + 常量导出 | **≈0** |

**这是「哪些规格书一个字都不用改」的最强答案：不是不用改，是整个 tag 不存在了。**

### 17.4 失误模式的方向对照

| 场景 | React 的失误 | Vue 的失误 |
| --- | --- | --- |
| 派生值 | 忘 `useMemo` → 更新**太多**（性能） | 忘 `computed` → 更新**太少**（🔴 正确性） |
| store 订阅 | 忘 selector → 重渲染（性能） | 忘 `storeToRefs` → 值不更新（🔴 正确性） |
| `queryKey` | 天然正确 | 忘 `computed` → 🔴 **静默不重新请求** |
| 组件外访问 store | 天然可用 | 🔴 抛错（但**报错明确**） |
| 动态路由清理 | 重建天然清空 | 🔴 残留（**第二次才暴露**） |
| 时序失败 | 🔴 **死锁/静默**（转圈、提示不弹） | 抛异常（**报错明确**） |
| 单测隔离 | 🔴 **顺序相关**（最难查） | 抛错（**容易修**） |

### 17.5 三条结论

**结论 1：权限架构的层次划分与框架无关。**

四层体验 + 一层安全，在两个框架里**结构完全相同**。
换框架只改变「每一层长什么样」，不改变「有几层、哪一层是边界」。

**结论 2：两边的失误方向系统性地相反。**

- React 更容易「更新太多」，Vue 更容易「更新太少」
- **在权限系统里 Vue 的方向更危险**（该消失的按钮没消失是功能 bug，多渲染几次只是慢）
- 但 React 更容易「失败得很静」（死锁、顺序相关的测试），Vue 更容易「失败得很响」

**任何一句「X 更适合权限系统」都会漏掉上面某一半。**

**结论 3：写起来更短的那一边，不一定是更难写错的那一边。**

| 主题 | 代码更短 | 更难写错 |
| --- | --- | --- |
| 分页同步 URL（第 10 节） | Vue | 打平 |
| `queryKey`（第 9 节） | 打平 | **React** |
| 权限判断函数（第 4 节） | Vue | 打平 |
| 动态路由（第 6 节） | Vue（增量更少代码） | **React**（重建自带清理） |
| 错误边界（第 12 节） | Vue | 打平（**限制相同**） |
| 单测隔离（第 14 节） | 打平 | **Vue** |
| 刷新时序（第 8 节） | 打平 | 各有各的失败模式 |

> **代码量和正确性是两个独立的维度。**
> 大部分框架对比只比第一个，而只有第二个会在半年后找上门。

---

## 附：还没验证的三件事

到 `vue-v1.0.0` 收口时回来填写，**分歧的地方比一致的地方有价值**。

| # | 待验证 | 在哪个 tag |
| --- | --- | --- |
| 1 | `watch` 是否还有「`await refetch()` 之后 store 未更新」的时序窗口（第 11 节） | `vue-v0.11.0` |
| 2 | `autoInsertSpaceInButton` 这个坑是不是真的会以「照抄 React 版无效属性」的形式再踩一次 | `vue-v0.2.0` |
| 3 | E2E 里除了三处例外，是否真的一个字都不用改 | `vue-v0.14.0` |
