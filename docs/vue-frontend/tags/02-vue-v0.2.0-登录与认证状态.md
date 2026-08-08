# vue-v0.2.0 — 登录、登出与认证状态

| 项 | 值 |
| --- | --- |
| 需求 | VE-1.1 ~ VE-1.7 |
| 关键 V-ADR | [003](../02-设计文档.md)、[006](../02-设计文档.md) |
| 预计耗时 | 2 ~ 3 小时 |
| 变更规模 | ~250 行 |
| 上一个 tag | `vue-v0.1.0` |
| React 对应 | [`fe-v0.3.0`](../../frontend/tags/03-fe-v0.3.0-登录与认证状态.md) |

> ⚠️ React 阶段这一步的前面还有整整一个 `fe-v0.2.0`（后端 Session + CSRF）。
> **本阶段它不存在**——后端早就准备好了，直接开始写登录页。

---

## 一、动手之前，先自己想清楚

1. 登录成功后，前端要把「token」存到哪里？**这是个陷阱问题。**
2. CSRF token 从哪来？第一次访问时 cookie 里还没有怎么办？
3. 登录页要不要维护自己的 `loading` / `error` 状态？还是交给别的东西管？
4. 登出时除了调接口，前端还要清什么？**列全**再往下看。

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/api/csrf.ts` | 读 cookie + 注入 `X-CSRFToken`（**从 React 版复制**） |
| 新建 | `src/types/auth.ts` | `User` / `MenuNode` / `Profile` |
| 新建 | `src/auth/api.ts` | `login` / `logout` / `fetchProfile` 请求函数 |
| 新建 | `src/auth/store.ts` | Pinia store |
| 新建 | `src/auth/useAuth.ts` | `useLogin` / `useLogout` |
| 新建 | `src/components/FullPageSpin.vue` | 全屏加载 |
| 新建 | `src/pages/Login.vue` | 登录页 |
| 修改 | `src/api/client.ts` | 挂 CSRF 拦截器 + 401 跳转钩子 |
| 修改 | `src/router/index.ts` | 加 `/login` 路由 + **最小认证守卫** |
| 修改 | `src/main.ts` | `VueQueryPlugin` |
| 修改 | `src/App.vue` | `<ConfigProvider>` |

### 📌 两处与规格书初稿不同的地方（已按 V-ADR-002 修正）

**1. store 的字段与 React 版 `fe-v0.3.0` 保持同形**

初稿写的是「本 tag 只放 user / status，`perms`/`menus` 是 `vue-v0.4.0` 的事」。
**改掉了**：React 版 `fe-v0.3.0` 的 store 里就有 `perms` / `menus`
（登录接口返回的本来就是完整 profile，存下来零成本），
而 [V-ADR-002](../02-设计文档.md) 要求控制变量——
两边 store 在同一阶段形状不同的话，`vue-v0.4.0` 的 diff 讲的故事
就和 `fe-v0.6.0` 的 diff 对不上了。

所以本 tag 的 store 直接是最终形状，`vue-v0.4.0` 只加 `can()` 和查询层。

**2. `types/auth.ts` 一步到位，不分两次长出来**

React 版的 `MenuNode` 在 `fe-v0.3.0` 只有 `{id, name, icon, url, permType, children}`，
到 `fe-v0.5.0` 才长出 `routePath` / `component` / `permCode`，`Profile` 才长出 `knownRoutes`
——因为那些字段是它自己在 `fe-v0.5.0` 加到后端的。

**Vue 版拿到的是已经完成的 API 契约**，类型应该如实描述接口返回什么。

> 📌 这是「两个 tag 消失了」的一个具体侧面：
> 消失的不只是工作量，还有**「类型定义分两次长出来」这个过程本身**。
> 接第三个前端时，契约是**给定的**而不是**协商出来的**。

---

## 三、接口契约

```ts
// src/auth/api.ts
export function login(username: string, password: string): Promise<void>
export function logout(): Promise<void>
export function ensureCsrfToken(): Promise<void>
```

后端接口（`fe-v0.2.0` 已实现，**本阶段直接用**）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/auth/csrf/` | 种一个 `csrftoken` cookie |
| `POST` | `/api/v1/auth/login/` | Session 登录 |
| `POST` | `/api/v1/auth/logout/` | 清 Session |
| `GET` | `/api/v1/auth/profile/` | 当前用户 + perms + menus |

---

## 四、⚠️ 容易写错的地方

### 1. 第一节第 1 问：**哪儿都不存**

```ts
// ❌ 这是最该抄的教程写法，也是最不该抄的
localStorage.setItem('token', res.data.access)
```

登录成功后**前端什么都不做**——凭证在 httpOnly Cookie 里，JS 根本读不到
（`F-ADR-002`）。前端唯一要做的是「拉一次 profile 确认自己是谁」。

如果你写下了任何 `localStorage` / `sessionStorage` 相关的代码，
说明还没接受这个模型。

### 2. CSRF token 的先有鸡还是先有蛋

第一节第 2 问。第一次访问时 cookie 里没有 `csrftoken`，
而登录是 `POST`——Django 会直接 403。

```ts
// src/auth/api.ts
export async function login(username: string, password: string) {
  await ensureCsrfToken()      // ⚠️ 必须先种一个
  await client.post('/auth/login/', { username, password })
}
```

⚠️ `ensureCsrfToken()` 要做**幂等**判断（cookie 里已有就不请求），
否则每次登录都多一个来回。

### 3. 🔴 `autoInsertSpaceInButton` —— 照抄 React 版会写出一个**无效属性**

React 版（`fe-v0.3.0` 踩过）：

```tsx
<ConfigProvider button={{ autoInsertSpace: false }}>
```

**照抄到 Vue 里是这样**：

```vue
<!-- ❌ antdv 4 里没有 button 这个 prop。不报错，也不生效 -->
<a-config-provider :button="{ autoInsertSpace: false }">
```

正确写法：

```vue
<!-- ✅ antdv 4 沿用 antd 4/5 的写法：顶层 prop -->
<a-config-provider :auto-insert-space-in-button="false">
```

> ⚠️ 不设的话，「登录」会渲染成「登 录」（中间插入一个空格），
> 于是所有按文本查找按钮的代码——**包括 `vue-v0.13.0` 的单测和 `vue-v0.14.0` 的 E2E**
> ——全部失效，而报错信息完全指不到原因。
>
> 📌 **这是 [04 对比文档](../04-React与Vue3做法对比.md)「待验证第 2 条」的现场。**
> 实现完回去把结论填上：**照抄导致的「配了但没生效」比完全没配更难查**——
> 因为你会认为「我明明配了」。

### 4. 表单：`v-model` 不需要受控组件那一套

```vue
<script setup lang="ts">
const formState = reactive({ username: '', password: '' })
</script>

<template>
  <a-form :model="formState" @finish="onSubmit">
    <a-form-item name="username" :rules="[{ required: true, message: '请输入用户名' }]">
      <a-input v-model:value="formState.username" />
    </a-form-item>
  </a-form>
</template>
```

⚠️ antdv 的 `a-input` 是 `v-model:value` 不是 `v-model`。
写成 `v-model` **不报错，输入框就是不响应**。

### 5. 第一节第 3 问：loading / error 交给 `useMutation`

```ts
const { mutate, isPending, error } = useMutation({
  mutationFn: () => login(formState.username, formState.password),
  onSuccess: () => router.replace(redirectTarget.value),
})
```

⚠️ **`useMutation` 的 `onSuccess` 在 v5 里仍然存在**（被移除的是 `useQuery` 的）。
两个框架的适配层在这一点上完全一致。

### 6. 登录失败提示：用后端的 `detail`

```ts
// ❌ 硬编码 → 两边文案会漂移，而且可能泄露「用户存在但密码错」
message.error('用户名或密码错误')

// ✅
message.error(err.response?.data?.detail ?? '登录失败')
```

后端已经保证不区分「用户不存在」和「密码错误」（`VE-1.7`）。
前端硬编码等于把这个安全设计架空了一半。

### 7. 🔴📌 第一节第 4 问：登出要清三样，**外加一次显式跳转**

```ts
onSettled: async () => {
  queryClient.clear()          // 1. ⚠️ 否则下一个用户会看到上一个用户的数据
  auth.reset()                 // 2. store 复位
  resetAuthRedirectGuard()     // 3. 401 去重标志复位
  await router.replace('/login')   // 🔴 4. **这一行 React 版没有**
}
```

**第 4 行是实测逼出来的。** 不加的话：

```
登出 → session 清了、store 清了、cookie 也没了
     → 但用户**仍然停在原页面上**，界面还是登录态的壳
```

根因是 [V-ADR-005](../02-设计文档.md) 的另一面——**它在初稿里被漏掉了**：

| | React | Vue |
| --- | --- | --- |
| 守卫是什么 | **组件**（`RequireAuth`），在渲染树里 | **导航流程的一环**（`beforeEach`） |
| `status` 变 `anonymous` 时 | 重新渲染 → `<Navigate>` **自动生效** | **没有导航发生 → 守卫根本不会运行** |
| 要写跳转代码吗 | ❌ 不需要 | ✅ **必须** |

> **React 的守卫是「状态的函数」，Vue 的守卫是「导航的钩子」。**
> 前者对状态变化天然响应，后者只在有人导航时才醒来。

→ 硬规则：**凡是「状态变了所以该换页面」的场景，Vue 都必须自己发起导航。**

⚠️ 这顺带解释了 401 为什么必须**注入一个跳转回调**而不能只清 store——**同一个原因**。

⚠️ **还有两样到后续 tag 才存在**：
`clearDynamicRoutes()`（`vue-v0.5.0`）和 `resetVersionWatcher()`（`vue-v0.11.0`）。
本 tag 先不写。

> 📌 到 `vue-v0.11.0` 时 Vue 版的登出会有**六件事**，React 版只有**四件**。
> 多出来的两件各有出处：
> - `clearDynamicRoutes()` ← 增量路由 API（[第 6 节](../04-React与Vue3做法对比.md#6-动态路由注册重建-vs-增量)）
> - `router.replace('/login')` ← 导航期守卫（[第 7 节](../04-React与Vue3做法对比.md#7-路由守卫渲染期-vs-导航期)）
>
> **两件都不是「Vue 更麻烦」，都是某个「拦得更早/更省事」的选择的账单。**

### 8. 🔴 认证守卫的落点：Vue 从这里就开始不一样了

React 版 `fe-v0.3.0` 用的是**组件**：

```tsx
<Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
```

Vue 版用**导航守卫**——[V-ADR-005](../02-设计文档.md) 的雏形已经出现在本 tag：

```ts
// ⚠️ 本 tag 只做「登没登录」，**刻意不管权限**。
//    权限判断 + profile 预加载 + 动态路由是 vue-v0.5.0 的 guard.ts。
//    两者职责分开，否则以后改一个会意外影响另一个。
router.beforeEach((to) => {
  if (to.path === '/login') return true
  const auth = useAuthStore()
  if (auth.status === 'anonymous') {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})
```

⚠️ 注意这里**没有**处理 `status === 'unknown'`——本 tag 的 profile 预加载
还在 `App.vue` 里（对应 React 的 `useBootstrapAuth`），
`unknown` 时直接放行，由页面自己显示 loading。

**`vue-v0.5.0` 会把这一段整个重写**：`unknown` 时在守卫里 `await` profile，
然后 `addRoute` + `return { ...to, replace: true }`。

> 📌 这是本阶段的一条暗线：**同一个职责，React 放在组件树里，Vue 放在导航流程里。**
> 差异从 `fe-v0.3.0` ↔ `vue-v0.2.0` 就开始了，到 `vue-v0.5.0` 完全展开。

### 9. `status` 三态，不是布尔

```ts
const status = ref<'unknown' | 'authenticated' | 'anonymous'>('unknown')
```

理由与 React 版**逐字相同**（[V-ADR-006](../02-设计文档.md)）：

> 「还没问过后端」≠「确定未登录」。用布尔的话初始 `false` 会被当成「未登录」，
> 应用启动瞬间闪一下登录页。

Vue 版多一条独立理由：`vue-v0.5.0` 的守卫靠 `status === 'unknown'`
判断「要不要拉 profile」。用布尔的话每次导航都会重拉，直接违反 `VNFR-7`。

---

## 五、卡住了看这里

<details>
<summary><b>提示：csrf.ts（与 React 版逐字相同）</b></summary>

```ts
function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`))
  return match ? decodeURIComponent(match[2]) : null
}

const SAFE_METHODS = new Set(['get', 'head', 'options', 'trace'])

export function attachCsrfToken(config: InternalAxiosRequestConfig) {
  if (SAFE_METHODS.has((config.method ?? 'get').toLowerCase())) return config
  const token = readCookie('csrftoken')
  if (token) config.headers.set('X-CSRFToken', token)
  return config
}
```

⚠️ `csrftoken` 必须是 **可读** 的（`CSRF_COOKIE_HTTPONLY = False`，`F-ADR-004`）。
设成 `True` 会让所有写请求 403。
</details>

<details>
<summary><b>提示：store 的最小形态</b></summary>

```ts
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const status = ref<'unknown' | 'authenticated' | 'anonymous'>('unknown')

  function setUser(u: User) { user.value = u; status.value = 'authenticated' }
  function reset() { user.value = null; status.value = 'anonymous' }

  return { user, status, setUser, reset }
})
```
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 正确账号登录 | 跳首页 |
| 2 | 错误密码 | 提示（**文案来自后端**） |
| 3 | 登录后开控制台执行 `document.cookie` | **看不到 `sessionid`**，能看到 `csrftoken` |
| 4 | 登录后 `localStorage` / `sessionStorage` | **空的** |
| 5 | 未登录直接访问 `/` | 跳 `/login` |
| 6 | 带 `?redirect=/tickets` 登录 | 登录后到 `/tickets` |
| 7 | 登出 | Cookie 清掉，回登录页 |
| 8 | 登出后按浏览器返回键 | **不能**看到上个用户的数据（Query 缓存已清） |
| 9 | 按钮文字 | 「登录」**不是**「登 录」 |
| 10 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ 用例 3、4 是 `FNFR-1` / `VNFR-1` 的现场验证，**每次都手动做一遍**，
不要因为「上次是对的」就跳过。

---

## 七、和我的实现对比什么

```bash
diff -u frontend/src/api/csrf.ts   frontend-vue/src/api/csrf.ts     # 期望：几乎无差异
diff -u frontend/src/auth/api.ts   frontend-vue/src/auth/api.ts     # 期望：几乎无差异
# Login.tsx vs Login.vue —— 这两个没法 diff，人肉对照
```

| 对比点 | 想一想 |
| --- | --- |
| `csrf.ts` 差了几行 | 差很多的话，是不是顺手「优化」了？ |
| 登出清了几样 | 少清一样，哪个用例会红？ |
| `autoInsertSpaceInButton` 写对了吗 | 跑用例 9 |
| store 里有没有混进 `perms` | 混进去的话 `vue-v0.4.0` 的 diff 就不干净了 |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `csrf.ts` | 🟢 **逐字相同** |
| `auth/api.ts` | 🟢 **逐字相同** |
| `types/auth.ts` | 🟡 内容相同，但 Vue **一步到位**（React 分 `fe-v0.3.0`/`fe-v0.5.0` 两次长出来） |
| store 形状 | 🟢 **相同**（V-ADR-002 要求对齐） |
| `status` 三态 | 🟢 决策相同，Vue 多一条独立理由 |
| 登录表单 | 🟡 `v-model:value` ← 受控组件 + `Form.useForm()` |
| loading / error | 🟢 都用 `useMutation`；⚠️ Vue 侧要写 `.value`（`login.isPending.value`） |
| 「已登录就跳走」 | 🟡 `watch` + `immediate` ← `useEffect` + 依赖数组 |
| 认证守卫落点 | 🔴 `router.beforeEach` ← `<RequireAuth>` 组件 |
| **登出后的跳转** | 🔴🔴 **Vue 必须显式 `router.replace`，React 不需要**（陷阱 7，实测发现） |
| `ConfigProvider` | 🔴 **API 位置不同**（`auto-insert-space-in-button` ← `button={{...}}`）。⚠️ 这是 **UI 库版本世代**差异，不是 Vue/React 差异 |
| `Spin` 的提示 prop | 🔴 `tip` ← `description`（同上，版本世代） |
| **后端改动** | 🟢 **0**（React 阶段这里前面有整整一个 `fe-v0.2.0`） |

**本 tag 的结论**：传输层（`csrf.ts` / `auth/api.ts`）**逐字复用**，
安全语义（httpOnly、不存 token、400 不是 401、开放重定向防护）**完全一致**。

真正的差异只有一处，而且**不在计划里**：
**认证守卫从组件挪到导航流程后，「状态变化」不再自动触发重定向。**
这是 `V-ADR-005` 初稿漏掉的代价，已回填设计文档与 04 对比文档第 7 节。

---

## 九、延伸思考

1. `F-ADR-003` 说「同域下 JWT 的无状态优势不成立」。
   换了前端框架之后，**这个论证有任何一处需要修改吗？**
   （提示：论证里出现过「React」这个词吗？）

2. 用例 3 在**单测里做不到**（jsdom 不实现 httpOnly 语义，断言会假绿）。
   这条限制在 Vue 版**也一样**。
   **能被单测验证的和不能被单测验证的，分界线在哪？**

3. 现在你有两个登录页了。用 `cs_manager` 分别登录 :5173 和 :5174，
   **同一个浏览器里两个 SPA 共享同一个 sessionid 吗？**
   为什么？这对「登出」意味着什么？
