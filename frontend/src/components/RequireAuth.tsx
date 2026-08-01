import type { ReactNode } from 'react'

import { Navigate, useLocation } from 'react-router'

import { useAuthStore } from '@/auth/store'

import { FullPageSpin } from './FullPageSpin'

/**
 * 认证守卫：只管「登没登录」。
 *
 * ⚠️ 刻意不管「有没有权限」——权限守卫是 fe-v0.7.0 的 PermissionGate。
 *    两者职责分开，否则以后改一个会意外影响另一个。
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  // 「还没问过后端」≠「确定未登录」。未知时不渲染任何东西，
  // 否则会闪一下登录页再跳回来。
  if (status === 'unknown') return <FullPageSpin />

  if (status === 'anonymous') {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }

  return <>{children}</>
}
