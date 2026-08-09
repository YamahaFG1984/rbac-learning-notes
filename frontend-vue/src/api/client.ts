import axios from 'axios'

import { attachCsrfToken } from './csrf'
import { watchRbacVersion } from './versionWatcher'

/**
 * 统一的 API 客户端。
 *
 * baseURL 是相对路径 '/api/v1' 而不是绝对地址——这是 F-ADR-002 的直接结果：
 * 前端只对自己的源发请求，由 Vite（开发）/ Nginx（生产）转发到 Django。
 *
 * ⚠️ 本文件与 React 版（frontend/src/api/client.ts）几乎逐字相同。
 *    axios 不认识 Vue 也不认识 React——这一层与框架无关。
 *
 * ⚠️ 403 分流、404 提示、X-RBAC-Version 比对分别属于
 *    vue-v0.12.0 / vue-v0.11.0。**不要提前写。**
 */
export const client = axios.create({
  baseURL: '/api/v1',
  // ⚠️ 不能少。同域下浏览器本会带 Cookie，但 axios 的 XHR 需要显式开启。
  //    忘了它的表现是「登录接口成功，之后所有请求 401」——
  //    看起来像后端问题，实际是 Cookie 根本没发出去。
  withCredentials: true,
  timeout: 15_000,
})

client.interceptors.request.use(attachCsrfToken)

// --------------------------------------------------------------------------- //
// 401 处理
//
// ⚠️ 这里**只**处理 401。403 由 vue-v0.12.0 的统一分流负责——
//    403 跳登录页会造成「登录 → 403 → 登录」的死循环（F-ADR-011）。
// --------------------------------------------------------------------------- //

/**
 * 会话过期时把用户送去登录页的回调，由 App 注入。
 *
 * ⚠️ 为什么用注入而不是直接 `import router`：
 *
 *    React 版的理由是**依赖方向**——`api/` 不许 import 路由。
 *    Vue 版**多一条理由**：Pinia 的 store 绑在 app 实例上，
 *    而本文件在 main.ts 里被 import，那时 `app.use(pinia)` 还没执行
 *    （V-ADR-003）。
 *
 *    同一个做法，两边的理由不同——这说明「注入」不是某个框架的技巧，
 *    而是「模块加载期 ≠ 应用运行期」这个普遍问题的通解。
 */
let onUnauthenticated: (() => void) | null = null

export function setUnauthenticatedHandler(handler: () => void) {
  onUnauthenticated = handler
}

/**
 * 并发去重：一个页面可能同时发 5 个请求，会话过期时会同时收到 5 个 401。
 * 不去重的话跳转会被触发 5 次，URL 变成
 * /login?redirect=/login?redirect=/login...
 */
let redirecting = false

export function resetAuthRedirectGuard() {
  redirecting = false
}

export function redirectToLoginOnce() {
  if (redirecting) return
  redirecting = true
  onUnauthenticated?.()
}

client.interceptors.response.use(
  (response) => {
    // 版本号搭在已有响应上，零额外请求（F-ADR-010）
    void watchRbacVersion(response)
    return response
  },
  (error: { response?: { status?: number } }) => {
    if (error.response) {
      /*
       * ⚠️ 错误响应也带版本号 —— 而且这恰恰是最需要它的时候：
       *    权限刚被撤销时，用户碰到的第一个响应往往就是 403。
       *
       *    漏掉这一支的表现：撤权后用户点按钮 → 403 → 提示「无权限」→
       *    但按钮**还在**，再点还是 403。用户会一直点。
       */
      void watchRbacVersion(error.response as never)
    }
    if (error.response?.status === 401) redirectToLoginOnce()

    // ⚠️ 一定要继续 reject。
    //    这里 return 一个 resolved promise 的话，调用方拿到的是
    //    「成功但 data 是 undefined」——错误被吞掉，页面显示空白，
    //    而且 Query 认为请求成功了，不会进 error 分支。
    return Promise.reject(error)
  },
)
