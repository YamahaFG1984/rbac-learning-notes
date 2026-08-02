import type { ReactNode } from 'react'

import { Navigate } from 'react-router'

import { usePermission } from '@/auth/usePermission'
import type { PermCode } from '@/constants/permissions'

/**
 * 路由级权限守卫。
 *
 * ⚠️⚠️ **这不是安全边界。**
 *
 *    perms 就在用户的浏览器内存里，控制台改成 ['*'] 只需要几秒；
 *    而且攻击者根本不必用这个前端——他可以直接 curl 你的 API。
 *
 *    模板版：「攻击者不点你的按钮，他直接发请求。」
 *    SPA 版：「攻击者不用你的路由，甚至不用你的前端。」
 *
 *    **路由守卫比隐藏按钮更容易造成错觉**，因为它写起来太像鉴权了。
 *
 *    唯一的安全边界是后端的 HasPerm + ScopedQuerysetMixin。
 *    fe-v0.16.0 有一条 E2E 专门证明这一点：篡改 store 让按钮出现，
 *    点下去仍然 403；甚至绕过前端直接调 API，还是 403。
 *
 * 那它有什么用？它挡的不是攻击者，是**误操作和坏链接**——
 * 用户点到一个进去必然报错的页面，体验很差。仅此而已。
 */
export function PermissionGate({
  perm,
  children,
}: {
  perm: PermCode | null
  children: ReactNode
}) {
  const can = usePermission()
  if (perm && !can(perm)) return <Navigate to="/403" replace />
  return <>{children}</>
}
