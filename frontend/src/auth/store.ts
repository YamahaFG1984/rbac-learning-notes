import { create } from 'zustand'

import type { MenuNode, Profile, User } from '@/types/auth'

/**
 * 认证与权限状态。
 *
 * status 是**三态**而不是布尔：前端不保存 token，它靠「调一次接口试试」
 * 来判断自己登没登录。所以应用刚启动时存在一个中间态——
 * 既不是「已登录」也不是「未登录」。
 *
 * 用布尔值的话，初始 false 会被当成「未登录」，应用启动瞬间闪一下登录页
 * 然后又跳回来。
 *
 * ⚠️ setProfile 是权限数据的**唯一写入口**（F-ADR-005）。
 *    从 fe-v0.6.0 起只允许 useProfileQuery 的 onSuccess 调用它。
 *    两处写入 = 两个真相源，很快就会不一致。
 */
export interface AuthState {
  user: User | null
  perms: string[]
  menus: MenuNode[]
  knownRoutes: string[]
  status: 'unknown' | 'authenticated' | 'anonymous'

  setProfile: (profile: Profile) => void
  reset: () => void
}

const EMPTY = {
  user: null,
  perms: [] as string[],
  menus: [] as MenuNode[],
  knownRoutes: [] as string[],
}

export const useAuthStore = create<AuthState>((set) => ({
  ...EMPTY,
  status: 'unknown',

  setProfile: (profile) =>
    set({
      user: profile.user,
      perms: profile.perms,
      menus: profile.menus,
      knownRoutes: profile.knownRoutes,
      status: 'authenticated',
    }),

  reset: () => set({ ...EMPTY, status: 'anonymous' }),
}))
