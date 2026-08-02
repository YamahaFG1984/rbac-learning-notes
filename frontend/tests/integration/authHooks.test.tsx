import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, renderHook, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { AuthBootstrap } from '@/auth/AuthBootstrap'
import { useAuthStore } from '@/auth/store'
import { useLogin, useLogout } from '@/auth/useAuth'
import { useProfileQuery } from '@/auth/useProfileQuery'
import { CS_MANAGER_PROFILE } from '@/test/fixtures'
import { setCurrentUser } from '@/test/msw/handlers'
import { server } from '@/test/msw/server'

/**
 * ⚠️ 每个测试新建一个 QueryClient。
 *
 *    模块级单例 + staleTime: Infinity 的组合会让测试 A 拉的 profile
 *    被测试 B 读到，出现「单独跑绿、一起跑红」。
 *
 *    对照后端 v0.16.0 的 tests/conftest.py 全局清缓存 fixture——
 *    **同一个问题的两种语言版本：有缓存就必须管测试隔离。**
 */
function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useProfileQuery', () => {
  it('拉到 profile 后写入 store（唯一写入口，F-ADR-005）', async () => {
    setCurrentUser('cs_manager')
    renderHook(() => useProfileQuery(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe('authenticated')
    })
    expect(useAuthStore.getState().perms).toEqual(CS_MANAGER_PROFILE.perms)
    expect(useAuthStore.getState().user?.username).toBe('cs_manager')
  })

  it('401 时把状态置为 anonymous，而不是停在 unknown', async () => {
    setCurrentUser(null)
    renderHook(() => useProfileQuery(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe('anonymous')
    })
    expect(useAuthStore.getState().perms).toEqual([])
  })
})

describe('useLogin / useLogout', () => {
  it('登录成功后 store 里有权限', async () => {
    setCurrentUser(null)
    const { result } = renderHook(() => useLogin(), { wrapper: wrapper() })

    result.current.mutate({ username: 'cs_staff', password: 'demo1234' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(useAuthStore.getState().perms).toContain('ticket:ticket:create')
    expect(useAuthStore.getState().perms).not.toContain('ticket:ticket:delete')
  })

  it('密码错误时 store 不被写入', async () => {
    setCurrentUser(null)
    const { result } = renderHook(() => useLogin(), { wrapper: wrapper() })

    result.current.mutate({ username: 'cs_staff', password: 'wrong' })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(useAuthStore.getState().status).toBe('unknown')
  })

  it('🔴 登出清空 store —— 否则界面还显示上一个用户', async () => {
    useAuthStore.getState().setProfile(CS_MANAGER_PROFILE)

    const { result } = renderHook(() => useLogout(), { wrapper: wrapper() })
    result.current.mutate()

    await waitFor(() => {
      expect(useAuthStore.getState().status).toBe('anonymous')
    })
    expect(useAuthStore.getState().perms).toEqual([])
    expect(useAuthStore.getState().menus).toEqual([])
  })
})

describe('AuthBootstrap', () => {
  it('🔴 状态未知时不渲染 children —— 未知 ≠ 允许', async () => {
    setCurrentUser('cs_manager')
    render(
      <AuthBootstrap>
        <div>业务界面</div>
      </AuthBootstrap>,
      { wrapper: wrapper() },
    )

    // 「还没问过后端」不等于「确定未登录」。
    // 先渲染的话，只要有人写出 `perms.length === 0 ? 显示全部 : ...`
    // （理由是「还没加载完就先都显示吧」），就会真的闪现越权内容
    expect(screen.queryByText('业务界面')).toBeNull()
    expect(screen.getByText(/正在加载权限信息/)).toBeTruthy()

    await waitFor(() => expect(screen.getByText('业务界面')).toBeTruthy())
  })

  it('🔴 401 不是错误 —— 未登录用户照样渲染 children（由路由送去登录页）', async () => {
    setCurrentUser(null)
    render(
      <AuthBootstrap>
        <div>业务界面</div>
      </AuthBootstrap>,
      { wrapper: wrapper() },
    )

    await waitFor(() => expect(screen.getByText('业务界面')).toBeTruthy())
    // 不该显示错误页
    expect(screen.queryByText(/无法加载你的权限信息/)).toBeNull()
  })

  it('网络错误 / 5xx 才显示错误页', async () => {
    server.use(
      http.get('/api/v1/auth/profile/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    render(
      <AuthBootstrap>
        <div>业务界面</div>
      </AuthBootstrap>,
      { wrapper: wrapper() },
    )

    await waitFor(() =>
      expect(screen.getByText(/无法加载你的权限信息/)).toBeTruthy(),
    )
    expect(screen.queryByText('业务界面')).toBeNull()
  })
})

describe('store 的三态', () => {
  it('setProfile 是唯一写入口，一次写全四样', () => {
    useAuthStore.getState().setProfile(CS_MANAGER_PROFILE)
    const s = useAuthStore.getState()
    expect(s.status).toBe('authenticated')
    expect(s.user?.username).toBe('cs_manager')
    expect(s.menus).toHaveLength(1)
    expect(s.knownRoutes.length).toBeGreaterThan(0)
  })

  it('reset 后是 anonymous，不是回到 unknown', () => {
    useAuthStore.getState().setProfile(CS_MANAGER_PROFILE)
    useAuthStore.getState().reset()
    // 回到 unknown 的话，RequireAuth 会以为「还在加载」而一直转圈
    expect(useAuthStore.getState().status).toBe('anonymous')
  })
})
