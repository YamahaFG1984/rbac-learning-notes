import { useEffect } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { App as AntdApp } from 'antd'
import { BrowserRouter, useNavigate } from 'react-router'

import { setForbiddenHandler, setUnauthenticatedHandler } from '@/api/client'
import { configureVersionWatcher } from '@/api/versionWatcher'
import { AuthBootstrap } from '@/auth/AuthBootstrap'
import { useAuthStore } from '@/auth/store'
import { PROFILE_QUERY_KEY } from '@/auth/useProfileQuery'
import { AppRouter } from '@/router/AppRouter'
import type { Profile } from '@/types/auth'

/** 把「会话过期怎么办」注入 axios 拦截器——避免 api 层直接依赖路由。 */
function UnauthenticatedBridge() {
  const navigate = useNavigate()
  const reset = useAuthStore((s) => s.reset)

  useEffect(() => {
    setUnauthenticatedHandler(() => {
      reset()
      const here = window.location.pathname + window.location.search
      navigate(`/login?redirect=${encodeURIComponent(here)}`, { replace: true })
    })
  }, [navigate, reset])

  return null
}

/**
 * 把「权限快照过期了怎么办」注入 axios 拦截器。
 *
 * 和 UnauthenticatedBridge 同一个手法：api 层不认识 Query 和 UI，
 * 由 App 在这里把能力注进去。
 */
function VersionWatcherBridge() {
  const queryClient = useQueryClient()
  const { message } = AntdApp.useApp()

  useEffect(() => {
    // ⚠️ 返回拉到的 profile 本身，不让调用方回头读 store ——
    //    store 的写入走 useEffect，refetch 解决时它还没更新（见 versionWatcher）
    const refetchProfile = async () => {
      await queryClient.refetchQueries({ queryKey: PROFILE_QUERY_KEY })
      return queryClient.getQueryData<Profile>(PROFILE_QUERY_KEY)
    }

    configureVersionWatcher({
      refetchProfile,
      // ⚠️ 非阻塞提示，不是 Modal —— 这不是需要用户确认的事。
      //    但也不能什么都不说：按钮突然消失、菜单少一项，
      //    用户会以为自己看错了或者系统抽风。
      notify: (text) => message.info(text),
    })

    // 403 兜底：用户停在静态页面时版本号感知不到，
    // 但他一点按钮就会撞上 403（见 client.ts 的说明）
    setForbiddenHandler(() => {
      void refetchProfile()
    })
  }, [queryClient, message])

  return null
}

/**
 * 层次很重要（见 AuthBootstrap 与 AppRouter 的注释）：
 *
 *     AuthBootstrap        ← 触发 profile 请求，确定认证状态与菜单
 *       └── AppRouter      ← 依赖 menus 动态注册路由
 *             ├── /login          （公开）
 *             └── RequireAuth     ← 依赖认证状态
 *                   └── AdminLayout
 *
 * AuthBootstrap 必须在最外层：
 *   · 放进 RequireAuth 内部 → 死锁（fe-v0.6.0 踩过）
 *   · AppRouter 放到它外面 → 刷新页面时路由表是空的 → 404（fe-v0.7.0 的时序陷阱）
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthBootstrap>
        <UnauthenticatedBridge />
        <VersionWatcherBridge />
        <AppRouter />
      </AuthBootstrap>
    </BrowserRouter>
  )
}
