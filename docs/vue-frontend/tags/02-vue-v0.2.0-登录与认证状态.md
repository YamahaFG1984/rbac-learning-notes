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
| 新建 | `src/auth/api.ts` | `login` / `logout` / `fetchProfile` 请求函数 |
| 新建 | `src/auth/store.ts` | Pinia store（**本 tag 只放 user / status**） |
| 新建 | `src/pages/Login.vue` | 登录页 |
| 修改 | `src/api/client.ts` | 挂 CSRF 拦截器 |
| 修改 | `src/router/index.ts` | 加 `/login` 路由 |
| 修改 | `src/App.vue` | `<a-config-provider>` |

> ⚠️ **本 tag 的 store 里不要放 `perms` / `menus`。** 那是 `vue-v0.4.0` 的事。
> 现在只需要「登没登录」和「登录的是谁」。

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

### 7. 第一节第 4 问：登出要清四样

```ts
async function doLogout() {
  await logout()                    // 1. 后端清 session
  auth.reset()                      // 2. store 复位
  queryClient.clear()               // 3. ⚠️ Query 缓存里还有上个用户的数据
  resetVersionWatcher()             // 4. ⚠️ 见 vue-v0.11.0
  router.replace('/login')
}
```

⚠️ **还差第五样，但它到 `vue-v0.5.0` 才存在**：`clearDynamicRoutes()`。
本 tag 还没有动态路由，先不写——但记住这里将来要加。

> 📌 React 版的登出只有四步，**永远不需要第五步**。
> 这就是 [04 对比文档第 6 节](../04-React与Vue3做法对比.md#6-动态路由注册重建-vs-增量)
> 说的「增量 API 多欠的那笔债」，它的第一张账单在这里。

### 8. `status` 三态，不是布尔

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
| 登出清理项 | 🟡 现在相同；`vue-v0.5.0` 起 Vue **多一项** |
| `status` 三态 | 🟢 决策相同，Vue 多一条独立理由 |
| 登录表单 | 🟡 `v-model` ← 受控组件 + `Form.useForm()` |
| loading / error | 🟢 都用 `useMutation`，`onSuccess` 两边都可用 |
| `ConfigProvider` | 🔴 **API 位置不同**（`auto-insert-space-in-button` ← `button={{...}}`）。⚠️ 这是 **UI 库版本世代**差异，不是 Vue/React 差异 |
| **后端改动** | 🟢 **0**（React 阶段这里前面有整整一个 `fe-v0.2.0`） |

**本 tag 的结论**：认证层的差异只在「表单怎么绑值」这一处，
而**传输、CSRF、安全语义全部逐字复用**。

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
