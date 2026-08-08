# vue-v0.12.0 — 401 / 403 / 404 全局分流与错误边界

| 项 | 值 |
| --- | --- |
| 需求 | VE-7.1 ~ VE-7.5 |
| 关键 V-ADR | [010](../02-设计文档.md) |
| 预计耗时 | 2 ~ 2.5 小时 |
| 变更规模 | ~200 行 |
| 上一个 tag | `vue-v0.11.0` |
| React 对应 | [`fe-v0.14.0`](../../frontend/tags/14-fe-v0.14.0-错误分流.md) |

---

## 一、动手之前，先自己想清楚

1. 401 和 403 的前端动作有什么不同？**写下来再往下看。**
2. 🔴 拦截器写成 `if (status === 401 || status === 403) redirectToLogin()` 会怎样？
3. 一个页面同时发 5 个请求，会话过期时收到 5 个 401。会跳几次登录页？
4. Vue 没有 `<ErrorBoundary>` 组件。**用什么替代？它能兜住 5xx 吗？**

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/api/errorHandlers.ts` | 统一分流（**从 React 版复制**） |
| 新建 | `src/components/AppErrorBoundary.vue` | `onErrorCaptured` |
| 新建 | `src/components/BootErrorFallback.vue` | 启动期错误 |
| 新建 | `src/components/ErrorResult.vue` | 错误结果页 |
| 修改 | `src/api/client.ts` | 挂 `handleApiError` |
| 修改 | `src/main.ts` | `app.config.errorHandler` |

---

## 三、分流表（与 React 版逐字相同）

| 状态码 | 动作 |
| --- | --- |
| **401** | 清 store → 跳登录（带 `redirect`）→ **不弹提示** → 并发去重 |
| **403** | 提示 + 重拉 profile（可能刚被撤权）→ **绝不跳登录页** |
| **404 / 400** | 拦截器**不处理**，交给调用方 |
| **429** | 显示后端的 `detail` |
| **5xx** | 错误边界整页替换，**不弹 toast** |
| 无 `response` | 「网络连接失败」，不是「服务器错误」 |

---

## 四、⚠️ 容易写错的地方

### 1. 🔴 第一节第 2 问：**「登录 → 403 → 登录」的死循环**

```ts
// 🔴 这是本项目最不能写的一行
if (status === 401 || status === 403) redirectToLogin()
```

```
用户点了无权限的按钮 → 403 → 跳登录页 → 重新登录 → 还是 403 → 又跳登录 → ...
```

**用户会以为账号坏了。** 而真实原因只是「他确实没这个权限」。

⚠️ 在 `errorHandlers.ts` 顶部把这段注释抄进去。**这是本 tag 存在的理由。**

### 2. 401 vs 403 的语义

| | 含义 | 用户该做什么 |
| --- | --- | --- |
| 401 | 未认证 / 会话过期 | **去登录** |
| 403 | 已认证但无权限 | **找管理员** |

搞混的话，用户会永远停在「权限不足」的提示上，而真实原因是他该去登录。

⚠️ 后端已经处理好了 DRF 把 401 降级成 403 的问题
（`apps/rbac/api/exceptions.py`，`F-ADR-011`）。**Vue 版直接受益。**
但要验证一次（自测用例 3）。

### 3. 第一节第 3 问：**只跳一次**，模块级 flag 去重

```ts
let redirecting = false

export function redirectToLoginOnce() {
  if (redirecting) return
  redirecting = true
  onUnauthenticated?.()
}

export function resetAuthRedirectGuard() { redirecting = false }
```

不去重的表现：URL 变成 `/login?redirect=/login?redirect=/login...`

⚠️ 登录成功后必须 `resetAuthRedirectGuard()`，否则下次会话过期不跳了。

### 4. 拦截器处理完**必须继续 reject**

```ts
handleApiError(error)
// ⚠️ 一定要继续 reject。
//    这里 return 一个 resolved promise 的话，调用方拿到的是
//    「成功但 data 是 undefined」——错误被吞掉，页面显示空白，
//    而且 Query 认为请求成功了，不会进 error 分支。
return Promise.reject(error)
```

**这条与框架无关**，React 版注释里已经记过。照抄。

### 5. 一律优先用后端的 `detail`

```ts
message.error(err.response?.data?.detail ?? '操作失败')
```

硬编码文案的话两边会漂移——后端改了提示，前端还是旧的。

### 6. 403 要重拉 profile（`VE-5.4` 的兜底）

```ts
case 403:
  message.warning(detail ?? '你没有执行该操作的权限')
  // ⚠️ 可能是权限刚被撤销。用户完全不发请求时版本号感知不到，
  //    403 是最后的兜底信号。
  void refetchProfileOnForbidden?.()
  break
```

⚠️ **不要**在这里 `redirectToLogin()`。看陷阱 1。

### 7. 🔴 第一节第 4 问：`onErrorCaptured` + 全局 handler，**但兜不住 5xx**

```vue
<!-- components/AppErrorBoundary.vue -->
<script setup lang="ts">
const error = ref<Error | null>(null)
onErrorCaptured((err) => {
  error.value = err as Error
  // ⚠️ 返回 false 阻止继续向上冒泡，否则全局 handler 会重复处理同一个错误
  return false
})
</script>

<template>
  <ErrorResult v-if="error" :error="error" @retry="error = null" />
  <slot v-else />
</template>
```

```ts
// main.ts —— 兜底上报
app.config.errorHandler = (err, instance, info) => {
  console.error('[app]', err, info)
}
```

**⚠️ 两边共有的限制，必须写清楚**：

`onErrorCaptured` 和 React 的 `componentDidCatch` **都不捕获**：

- 事件处理器里的错误（`@click` 里 throw）
- `setTimeout` / Promise 里的错误
- 异步 `queryFn` 的 reject

所以 **5xx 不能靠错误边界兜住**——API 错误走 axios 拦截器那条路，
错误边界管的是**渲染崩溃**。

> 📌 **这个限制不是框架的选择，是「同步渲染栈之外的错误无法被组件捕获」这个事实。**
> 换框架改变不了它。React 版注释里已经写过同一句话。
>
> [04 对比文档第 12 节](../04-React与Vue3做法对比.md#12-错误边界react-唯一的-class-vs-vue-的两个钩子)：
> **实现不同，限制相同。** 这类地方值得特别标注——
> 它们是真正的约束，不是可以通过选型绕开的东西。

### 8. 5xx 走整页替换而不是 toast

```
500 意味着服务端炸了，页面上的数据可能是半截的。
弹个 toast 然后让用户继续在坏掉的界面上点，比整页替换更糟——
他会以为「只是这一次失败了」，接着基于错误的数据做决定。
```

实现：给 `VueQueryPlugin` 配全局 `onError`，5xx 时抛到边界或直接切换整页状态。

### 9. `ResourceNotFound` 的文案不泄露信息

```
「工单不存在或你无权访问」
```

⚠️ **不要**写成两种情况分开的文案。后端 `ADR-009` 用 404 就是为了不泄露存在性，
前端分开写等于把这个设计架空了。

---

## 五、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 后端删掉 session（模拟过期），点任意按钮 | 跳登录页，**不弹一串红色提示** |
| 2 | 🔴 点一个无权限的按钮（Devtools 改 perms 让它出现） | 提示无权限，**绝不跳登录页** |
| 3 | 未登录直接请求 `/api/v1/tickets/` | **401**，不是 403 |
| 4 | 一个页面同时 5 个请求都 401 | **只跳一次**，URL 干净 |
| 5 | 登录成功后再次会话过期 | 还能跳（`resetAuthRedirectGuard` 生效） |
| 6 | 访问范围外的工单 | 「不存在或你无权访问」 |
| 7 | 后端造一个 500 | **整页错误 + 重试按钮**，不是 toast |
| 8 | 断网 | 「网络连接失败」，不是「服务器错误」 |
| 9 | 组件里故意 `throw` | 边界接住，其余页面照常 |
| 10 | 接用例 9 | 全局 handler **没有**重复处理（`return false` 生效） |
| 11 | 403 之后 | profile 被重拉（`VE-5.4`） |
| 12 | 后端 `pytest` / React 版单测 | 全绿 |

---

## 六、和我的实现对比什么

```bash
diff -u frontend/src/api/errorHandlers.ts frontend-vue/src/api/errorHandlers.ts
```

**期望：几乎逐字相同。** 差异只在「怎么弹提示」（`message` 的 import 来源）。

| 对比点 | 想一想 |
| --- | --- |
| 403 会跳登录页吗 | 跑用例 2 |
| 401 去重了吗 | 跑用例 4 |
| 处理完继续 reject 了吗 | 不 reject 的话，页面会显示什么？ |
| `return false` 写了吗 | 跑用例 10 |
| 错误边界能兜住 5xx 吗 | **不能**——你的 5xx 走的是哪条路？ |

---

## 七、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `errorHandlers.ts` | 🟢 **几乎逐字相同** |
| 401/403/404 分流表 | 🟢 **逐字相同** |
| 401 并发去重 | 🟢 **逐字相同**（模块级 flag，与框架无关） |
| 必须继续 reject | 🟢 **相同** |
| 404 文案 | 🟢 **必须逐字相同**（E2E 断言） |
| **错误边界实现** | 🔴 `onErrorCaptured` + `app.config.errorHandler` ← **class 组件** |
| **错误边界的限制** | 🟢🟢 **完全相同**（都兜不住异步和事件处理器） |
| 冒泡控制 | 🔴 Vue 要 `return false`；React 捕获即停止 |

**本 tag 的结论**：错误处理层是「实现不同、约束相同」的典型。
**约束相同**比「实现不同」重要得多——它说明这些限制来自 JS 的执行模型，
不来自框架。

---

## 八、延伸思考

1. React 的错误边界**必须写 class**，Vue 的是普通 composition 钩子。
   **这是 Vue 的优势吗？** 想清楚：这个 class 在整个项目里出现几次？
   它带来的实际成本是多少？

2. 两边的错误边界**都兜不住异步错误**。
   **有没有框架真的能兜住？** 如果没有，为什么？
   （提示：想想「捕获」这个动作发生在调用栈的什么位置。）

3. 陷阱 1 那行代码（`401 || 403` 都跳登录）是 SPA 里的高频 bug。
   **为什么模板版不会有这个问题？**
   这是「SPA 必须精确区分而模板版可以含糊」的又一个例子——
   还能想到别的例子吗？
