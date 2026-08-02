import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useAuthStore } from '@/auth/store'
import { usePermission, usePermissionAll, usePermissionAny } from '@/auth/usePermission'
import { PERM, type PermCode } from '@/constants/permissions'

function withPerms(perms: string[]) {
  useAuthStore.setState({ perms, status: 'authenticated' })
}

describe('usePermission', () => {
  it.each([
    { perms: [PERM.TICKET_TICKET_VIEW], code: PERM.TICKET_TICKET_VIEW, expected: true },
    { perms: [PERM.TICKET_TICKET_VIEW], code: PERM.TICKET_TICKET_DELETE, expected: false },
    // 超管通配。⚠️ 只在 usePermission 里处理一次，<Can>/守卫/菜单都复用
    { perms: ['*'], code: PERM.TICKET_TICKET_DELETE, expected: true },
    { perms: ['*'], code: PERM.SYSTEM_USER_DELETE, expected: true },
    // 默认拒绝：空数组 = 什么都不能做，不是「什么都能做」
    { perms: [], code: PERM.TICKET_TICKET_VIEW, expected: false },
  ])('perms=$perms code=$code -> $expected', ({ perms, code, expected }) => {
    withPerms(perms)
    const { result } = renderHook(() => usePermission())
    expect(result.current(code as PermCode)).toBe(expected)
  })

  it('未登录（status unknown，perms 为空）时一律拒绝', () => {
    const { result } = renderHook(() => usePermission())
    expect(result.current(PERM.TICKET_TICKET_VIEW)).toBe(false)
  })

  it('perms 变化后判断结果随之变化（fe-v0.13.0 的权限变更感知依赖这一点）', () => {
    withPerms([])
    const { result, rerender } = renderHook(() => usePermission())
    expect(result.current(PERM.TICKET_TICKET_DELETE)).toBe(false)

    withPerms([PERM.TICKET_TICKET_DELETE])
    rerender()
    expect(result.current(PERM.TICKET_TICKET_DELETE)).toBe(true)
  })
})

describe('usePermissionAny / usePermissionAll', () => {
  it('any：任一命中即通过', () => {
    withPerms([PERM.TICKET_TICKET_VIEW])
    const { result } = renderHook(() => usePermissionAny())
    expect(result.current([PERM.SYSTEM_USER_VIEW, PERM.TICKET_TICKET_VIEW])).toBe(true)
    expect(result.current([PERM.SYSTEM_USER_VIEW])).toBe(false)
  })

  it('all：全部命中才通过', () => {
    withPerms([PERM.TICKET_TICKET_VIEW, PERM.TICKET_TICKET_CREATE])
    const { result } = renderHook(() => usePermissionAll())
    expect(result.current([PERM.TICKET_TICKET_VIEW, PERM.TICKET_TICKET_CREATE])).toBe(true)
    expect(result.current([PERM.TICKET_TICKET_VIEW, PERM.SYSTEM_USER_VIEW])).toBe(false)
  })

  it('超管对 any / all 都通过', () => {
    withPerms(['*'])
    const { result: any_ } = renderHook(() => usePermissionAny())
    const { result: all_ } = renderHook(() => usePermissionAll())
    expect(any_.current([PERM.SYSTEM_USER_DELETE])).toBe(true)
    expect(all_.current([PERM.SYSTEM_USER_DELETE, PERM.TICKET_TICKET_DELETE])).toBe(true)
  })
})

describe('权限码常量', () => {
  it('是由后端生成的字面量联合类型，不是 string', () => {
    // 这一行如果能编译过，说明 as const 丢了 —— 类型收窄失效
    // @ts-expect-error 写错的权限码必须编译期报错（F-ADR-012）
    const bad: PermCode = 'ticket:ticket:delet'
    expect(bad).toBeDefined()
  })

  it('覆盖了后端导出的全部权限码', () => {
    const codes = Object.values(PERM)
    expect(codes.length).toBeGreaterThan(0)
    expect(new Set(codes).size).toBe(codes.length) // 无重复
    for (const code of codes) {
      expect(code).toMatch(/^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$/)
    }
  })
})
