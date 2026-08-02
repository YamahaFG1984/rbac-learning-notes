import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  client,
  redirectToLoginOnce,
  resetAuthRedirectGuard,
} from '@/api/client'
import { configureErrorHandlers } from '@/api/errorHandlers'
import { setUnauthenticatedHandler } from '@/api/client'
import { setCurrentUser } from '@/test/msw/handlers'

/**
 * 集成层：请求**真的发出去**，经过真实的 axios 拦截器，由 MSW 在网络层拦住。
 *
 * ⚠️ 这是 `vi.mock('axios')` 测不到的部分。
 *    我们有一半的权限逻辑在拦截器里（CSRF 注入、401 分流、403 兜底、
 *    版本号比对）——mock 掉 axios 之后它们一行都不会执行，而测试是绿的。
 */

let redirectToLogin: ReturnType<typeof vi.fn>
let refetchProfile: ReturnType<typeof vi.fn>
let warn: ReturnType<typeof vi.fn>
let error: ReturnType<typeof vi.fn>

beforeEach(() => {
  redirectToLogin = vi.fn()
  refetchProfile = vi.fn()
  warn = vi.fn()
  error = vi.fn()
  configureErrorHandlers({ redirectToLogin, refetchProfile, warn, error })
  resetAuthRedirectGuard()
})

describe('登录', () => {
  it('成功后拿到 profile', async () => {
    const { data } = await client.post('/auth/login/', {
      username: 'cs_manager',
      password: 'demo1234',
    })
    expect(data.user.username).toBe('cs_manager')
    expect(data.perms).toContain('ticket:ticket:delete')
  })

  it('密码错误返回 400，且用的是后端的文案', async () => {
    await expect(
      client.post('/auth/login/', { username: 'cs_manager', password: 'wrong' }),
    ).rejects.toMatchObject({ response: { status: 400 } })

    // 400 交给调用方映射到表单，不弹全局 toast
    expect(error).not.toHaveBeenCalled()
    expect(warn).not.toHaveBeenCalled()
  })
})

describe('🔴 401 与 403 走的是两条完全不同的路', () => {
  it('401 触发跳登录页', async () => {
    setCurrentUser(null)
    await expect(client.get('/auth/profile/')).rejects.toBeTruthy()
    expect(redirectToLogin).toHaveBeenCalled()
  })

  it('🔴 403 **不**跳登录页', async () => {
    await expect(client.get('/__test__/403/')).rejects.toBeTruthy()

    expect(redirectToLogin).not.toHaveBeenCalled()
    // 用后端说的话，不是前端硬编码的
    expect(warn).toHaveBeenCalledWith('你没有该操作的权限')
    // 顺带重拉 profile —— 可能是权限刚被撤销
    expect(refetchProfile).toHaveBeenCalled()
  })

  it('🔴 多个请求同时 401，只跳一次', async () => {
    setCurrentUser(null)
    let redirects = 0
    setUnauthenticatedHandler(() => {
      redirects += 1
    })
    configureErrorHandlers({
      redirectToLogin: redirectToLoginOnce,
      refetchProfile,
      warn,
      error,
    })

    await Promise.allSettled([
      client.get('/auth/profile/'),
      client.get('/auth/profile/'),
      client.get('/auth/profile/'),
      client.get('/auth/profile/'),
      client.get('/auth/profile/'),
    ])

    // 不去重的话 URL 会变成 /login?redirect=/login?redirect=/login...
    expect(redirects).toBe(1)
  })
})

describe('其余状态码', () => {
  it('404 完全不处理，原样抛给调用方', async () => {
    await expect(client.get('/__test__/404/')).rejects.toMatchObject({
      response: { status: 404 },
    })
    expect(warn).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    expect(redirectToLogin).not.toHaveBeenCalled()
  })

  it('429 显示后端的限流文案', async () => {
    await expect(client.get('/__test__/429/')).rejects.toBeTruthy()
    expect(warn).toHaveBeenCalledWith('登录失败次数过多，请 15 分钟后再试')
  })

  it('5xx 不弹 toast（交给错误边界整页替换）', async () => {
    await expect(client.get('/__test__/500/')).rejects.toBeTruthy()
    expect(error).not.toHaveBeenCalled()
    expect(warn).not.toHaveBeenCalled()
  })

  it('网络错误与服务端错误区分开', async () => {
    await expect(client.get('/__test__/network/')).rejects.toBeTruthy()
    expect(error).toHaveBeenCalledWith('网络连接失败，请检查网络后重试')
  })
})

describe('🔴 错误也必须继续 reject', () => {
  it('拦截器处理完之后，调用方仍然拿得到 error', async () => {
    // 拦截器 return 一个 resolved promise 的话，调用方拿到的是
    // 「成功但 data 是 undefined」，页面空白且 Query 不进 error 分支，
    // fe-v0.11.0 那套「404 整页替换」全部失效
    const result = await client.get('/__test__/404/').then(
      () => 'resolved',
      () => 'rejected',
    )
    expect(result).toBe('rejected')
  })
})
