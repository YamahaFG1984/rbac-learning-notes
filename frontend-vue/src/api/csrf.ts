import type { InternalAxiosRequestConfig } from 'axios'

/**
 * ⚠️ 本文件与 React 版（frontend/src/api/csrf.ts）**逐字相同**。
 *
 *    它读的是 document.cookie、写的是 HTTP 头——两样东西都不认识
 *    Vue 和 React。CSRF 这一层与框架完全无关。
 */

const SAFE_METHODS = new Set(['get', 'head', 'options', 'trace'])

export function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${name}=([^;]*)`),
  )
  return match?.[1] ? decodeURIComponent(match[1]) : null
}

/**
 * 给写请求注入 CSRF token。
 *
 * ⚠️ 每次请求都**重新读 cookie**，不能在启动时读一次存起来——
 *    登录成功后后端会 rotate_token()，缓存住旧值会导致所有写请求 403，
 *    而且报错信息完全指不到原因。
 */
export function attachCsrfToken(config: InternalAxiosRequestConfig) {
  const method = (config.method ?? 'get').toLowerCase()
  if (!SAFE_METHODS.has(method)) {
    config.headers.set('X-CSRFToken', getCookie('csrftoken') ?? '')
  }
  return config
}
