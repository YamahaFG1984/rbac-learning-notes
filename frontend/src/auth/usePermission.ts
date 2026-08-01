import { useCallback } from 'react'

import type { PermCode } from '@/constants/permissions'

import { useAuthStore } from './store'

/** 超管的通配。**只在本文件处理一次**——<Can>、路由守卫、菜单都调这里。 */
const WILDCARD = '*'

/**
 * 唯一的权限判断函数。
 *
 * 参数类型是 PermCode 而不是 string（F-ADR-012）——写错的权限码编译期就报错，
 * 不会像模板版那样静默地不渲染按钮。
 */
export function usePermission() {
  const perms = useAuthStore((s) => s.perms)

  return useCallback(
    (code: PermCode) => perms.includes(WILDCARD) || perms.includes(code),
    [perms],
  )
}

export function usePermissionAny() {
  const can = usePermission()
  return useCallback((codes: PermCode[]) => codes.some(can), [can])
}

export function usePermissionAll() {
  const can = usePermission()
  return useCallback((codes: PermCode[]) => codes.every(can), [can])
}
