import axios, { type AxiosError } from 'axios'

import { attachCsrfToken } from './csrf'
import { handleApiError } from './errorHandlers'
import { watchRbacVersion } from './versionWatcher'

/**
 * 统一的 API 客户端。
 *
 * baseURL 是相对路径 '/api/v1' 而不是绝对地址——这是 F-ADR-002 的直接结果：
 * 前端只对自己的源发请求，由 Vite（开发）/ Nginx（生产）转发到 Django。
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
// ⚠️ 这里**只**处理 401。403 由 fe-v0.14.0 的统一分流负责——
//    403 跳登录页会造成「登录 → 403 → 登录」的死循环（F-ADR-011）。
// --------------------------------------------------------------------------- //

/** 会话过期时把用户送去登录页的回调，由 App 注入（避免这里 import 路由） */
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

/** 供 errorHandlers 调用：401 跳登录页，已做并发去重 */
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
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response) {
      // ⚠️ 错误响应也带版本号 —— 而且这恰恰是最需要它的时候：
      //    权限刚被撤销时，用户碰到的第一个响应往往就是 403。
      void watchRbacVersion(error.response)
    }

    handleApiError(error)

    // ⚠️ 一定要继续 reject。
    //    这里 return 一个 resolved promise 的话，调用方拿到的是
    //    「成功但 data 是 undefined」——错误被吞掉，页面显示空白，
    //    而且 Query 认为请求成功了，不会进 error 分支。
    return Promise.reject(error)
  },
)
