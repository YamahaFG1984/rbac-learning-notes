import { useEffect } from 'react'

import { BrowserRouter, useNavigate } from 'react-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { AuthBootstrap } from '@/auth/AuthBootstrap'
import { useAuthStore } from '@/auth/store'
import { AppRouter } from '@/router/AppRouter'

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
        <AppRouter />
      </AuthBootstrap>
    </BrowserRouter>
  )
}
