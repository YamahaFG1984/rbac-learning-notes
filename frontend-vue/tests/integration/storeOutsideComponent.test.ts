import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { client } from '@/api/client'
import { useAuthStore } from '@/auth/store'
import { fetchProfileIntoStore } from '@/auth/useProfileQuery'
import { setCurrentUser } from '@/test/msw/handlers'

/**
 * 🔴🔴 **本文件在 React 版里不存在** —— 它测的是 `VE-2.6` / `V-ADR-003`。
 *
 * Zustand 的 store 是模块级单例，`getState()` 随时可调，
 * 「组件外访问 store」在 React 版根本不是一个问题。
 *
 * Pinia 的 store 绑在 app 实例上，`useAuthStore()` 在
 * `app.use(pinia)` 之前调用会抛：
 *
 *   [🍍]: "getActivePinia()" was called but there was no active Pinia.
 *
 * 而 `api/client.ts` 的拦截器、`router/guard.ts` 的守卫**都在组件外**。
 */
beforeEach(() => setActivePinia(createPinia()))

describe('VE-2.6：组件外访问 store', () => {
  it('🔴 拦截器执行时能安全读到 store（延迟调用，不在模块顶层）', async () => {
    setCurrentUser('cs_manager')
    // 请求真的发出去，经过真实的 request 拦截器 —— 它内部会 useAuthStore()
    await expect(client.get('/auth/profile/')).resolves.toBeTruthy()
  })

  it('🔴 fetchProfileIntoStore 是命令式的，守卫（组件外）能直接用', async () => {
    setCurrentUser('cs_manager')
    const profile = await fetchProfileIntoStore()

    expect(profile.user.username).toBe('cs_manager')
    // ⚠️ 它**同步**写完 store 才 resolve —— 这正是 vue-v0.11.0 实测的结论：
    //    React 的「await refetch() 之后 store 还是旧值」在 Vue 版不存在，
    //    但原因是这条命令式路径，不是 watch 更快。
    expect(useAuthStore().perms).toContain('ticket:ticket:delete')
    expect(useAuthStore().status).toBe('authenticated')
  })

  it('🔴 失败时 status 必须落到终态，否则守卫会无限重定向', async () => {
    setCurrentUser(null)
    await expect(fetchProfileIntoStore()).rejects.toBeTruthy()

    // 留在 'unknown' 的话：守卫看到 unknown → 拉 profile → 失败 →
    // 还是 unknown → return {...to} 重新导航 → 守卫又看到 unknown → 无限循环
    expect(useAuthStore().status).toBe('anonymous')
  })

  it('401 不被当成「引导失败」（它是正常流程）', async () => {
    setCurrentUser(null)
    const { bootError } = await import('@/auth/useProfileQuery')
    await fetchProfileIntoStore().catch(() => {})
    expect(bootError.value).toBeNull()
  })
})

describe('bootError 的分支', () => {
  it('🔴 非 401 的失败才算「引导失败」（VE-2.4 要显示可重试错误页）', async () => {
    const { bootError } = await import('@/auth/useProfileQuery')
    const { server } = await import('@/test/msw/server')
    const { http, HttpResponse } = await import('msw')

    server.use(
      http.get('*/api/v1/auth/profile/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    await fetchProfileIntoStore().catch(() => {})

    // 500 → 显示错误页；401 → 由守卫送去登录页（上一条用例）
    expect(bootError.value).not.toBeNull()
    expect(useAuthStore().status).toBe('anonymous')
  })

  it('成功后清掉上一次的 bootError', async () => {
    const { bootError } = await import('@/auth/useProfileQuery')
    bootError.value = new Error('旧的')
    setCurrentUser('cs_manager')
    await fetchProfileIntoStore()
    expect(bootError.value).toBeNull()
  })
})
