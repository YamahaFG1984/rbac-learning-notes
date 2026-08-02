import axios, { type AxiosError } from 'axios'

import { attachCsrfToken } from './csrf'
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

/**
 * 收到 403 时的兜底：强制重拉 profile。
 *
 * ⚠️ 版本号方案有一个盲区：**用户完全不发请求时感知不到**。
 *    他停在一个静态页面上，权限被撤了，屏幕上的按钮还在。
 *
 *    但只要他**点了那个按钮**，就会收到 403 —— 这正是兜底时机。
 *    即使版本号漏了，用户点一次就能恢复到正确状态。
 */
let onForbidden: (() => void) | null = null

export function setForbiddenHandler(handler: () => void) {
  onForbidden = handler
}

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
  (response) => {
    // 版本号搭在已有响应上，零额外请求（F-ADR-010）
    void watchRbacVersion(response)
    return response
  },
  (error: AxiosError) => {
    if (error.response) {
      // ⚠️ 错误响应也带版本号 —— 而且这恰恰是最需要它的时候：
      //    权限刚被撤销时，用户碰到的第一个响应往往就是 403。
      void watchRbacVersion(error.response)
    }
    if (error.response?.status === 401 && !redirecting) {
      redirecting = true
      onUnauthenticated?.()
    }
    if (error.response?.status === 403) {
      onForbidden?.()
    }
    return Promise.reject(error)
  },
)
