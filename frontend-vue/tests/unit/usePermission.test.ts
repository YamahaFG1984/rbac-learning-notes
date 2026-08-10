import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/auth/store'
import { usePermission } from '@/auth/usePermission'
import { PERM } from '@/constants/permissions'
import { PROFILES } from '@/test/fixtures'

/**
 * ⚠️ 每个用例重建 Pinia —— 与 React 版「手动 reset Zustand」是**相反的麻烦**。
 *    忘了的话 Vue 会**立即抛错**，React 会产生**顺序相关**的测试（更难查）。
 */
beforeEach(() => setActivePinia(createPinia()))

describe('usePermission —— 唯一的权限判断入口', () => {
  it('未登录时任何权限都为 false（默认拒绝）', () => {
    const { can } = usePermission()
    expect(can(PERM.TICKET_TICKET_VIEW)).toBe(false)
  })

  it('精确匹配', () => {
    useAuthStore().setProfile(PROFILES.cs_staff)
    const { can } = usePermission()
    expect(can(PERM.TICKET_TICKET_VIEW)).toBe(true)
    expect(can(PERM.TICKET_TICKET_DELETE)).toBe(false)
  })

  it('🔴 超管的 ["*"] 通配 —— 只在 store.can 里处理一次', () => {
    useAuthStore().setProfile(PROFILES.superadmin)
    const { can } = usePermission()
    expect(can(PERM.TICKET_TICKET_DELETE)).toBe(true)
    expect(can(PERM.SYSTEM_USER_DELETE)).toBe(true)
  })

  it('canAny / canAll', () => {
    useAuthStore().setProfile(PROFILES.cs_staff)
    const { canAny, canAll } = usePermission()
    expect(canAny([PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_VIEW])).toBe(true)
    expect(canAll([PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_VIEW])).toBe(false)
    expect(canAll([PERM.TICKET_TICKET_VIEW])).toBe(true)
  })

  it('🔴 reset 之后回到默认拒绝', () => {
    const auth = useAuthStore()
    auth.setProfile(PROFILES.superadmin)
    auth.reset()
    expect(usePermission().can(PERM.TICKET_TICKET_VIEW)).toBe(false)
    expect(auth.status).toBe('anonymous')  // ⚠️ 终态，不是 unknown
  })
})
