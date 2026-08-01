import axios, { type AxiosError } from 'axios'

import { attachCsrfToken } from './csrf'

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

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !redirecting) {
      redirecting = true
      onUnauthenticated?.()
    }
    return Promise.reject(error)
  },
)
