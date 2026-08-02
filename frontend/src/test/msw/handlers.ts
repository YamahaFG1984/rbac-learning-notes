import { http, HttpResponse } from 'msw'

import { PROFILES } from '../fixtures'

/**
 * ⚠️ MSW 拦的是**网络层**，不是 axios。
 *
 *    `vi.mock('axios')` 会把我们**一半的权限逻辑**跳过去：
 *    CSRF 注入、401 分流、403 兜底、版本号比对——全在拦截器里。
 *    mock 掉 axios 之后那些代码一行都不会执行，测试却是绿的。
 *
 *    MSW 让请求正常发出、正常经过拦截器，只是在最后一刻拦住。
 */

/** 当前登录的人。测试用 setCurrentUser 切换。 */
let currentUser: string | null = 'cs_manager'

/** 服务端的 RBAC 版本号（fe-v0.13.0）。 */
let rbacVersion = 1

export function setCurrentUser(username: string | null) {
  currentUser = username
}

export function bumpRbacVersion() {
  rbacVersion += 1
}

export function resetMswState() {
  currentUser = 'cs_manager'
  rbacVersion = 1
}

/** 所有 API 响应都带版本号头，和真后端的中间件一致 */
function withVersion(body: unknown, init: { status?: number } = {}) {
  return HttpResponse.json(body, {
    ...init,
    headers: { 'X-RBAC-Version': String(rbacVersion) },
  })
}

export const handlers = [
  http.get('/api/v1/auth/profile/', () => {
    if (!currentUser) {
      return withVersion({ detail: '身份认证信息未提供。' }, { status: 401 })
    }
    return withVersion(PROFILES[currentUser])
  }),

  http.get('/api/v1/auth/csrf/', () =>
    HttpResponse.json({ detail: 'ok' }, { headers: { 'Set-Cookie': 'csrftoken=t' } }),
  ),

  http.post('/api/v1/auth/login/', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (body.password !== 'demo1234') {
      // 后端的人话文案。前端不硬编码自己的一套（fe-v0.14.0 陷阱 7）
      return withVersion({ detail: '用户名或密码错误' }, { status: 400 })
    }
    currentUser = body.username
    return withVersion(PROFILES[body.username])
  }),

  http.post('/api/v1/auth/logout/', () => {
    currentUser = null
    return withVersion({ detail: 'ok' })
  }),

  // 各种错误状态码，供 fe-v0.14.0 的分流测试使用
  http.get('/api/v1/__test__/403/', () =>
    withVersion({ detail: '你没有该操作的权限' }, { status: 403 }),
  ),
  http.get('/api/v1/__test__/404/', () =>
    withVersion({ detail: '未找到。' }, { status: 404 }),
  ),
  http.get('/api/v1/__test__/429/', () =>
    withVersion({ detail: '登录失败次数过多，请 15 分钟后再试' }, { status: 429 }),
  ),
  http.get('/api/v1/__test__/500/', () =>
    withVersion({ detail: '服务器错误' }, { status: 500 }),
  ),
  http.get('/api/v1/__test__/network/', () => HttpResponse.error()),
]
