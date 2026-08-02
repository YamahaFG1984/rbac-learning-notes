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

/**
 * 🎯 只在 E2E 构建里把 store 挂到 window 上。
 *
 * fe-v0.16.0 的核心测试要**篡改**权限，证明前端的三层体验
 * （路由守卫、菜单、按钮）全部可以被绕过，而系统依然安全。
 *
 * ⚠️ 「为了测试而降低安全」吗？**不是。**
 *
 *    攻击者本来就能做到同样的事，而且不需要这个变量：
 *    React DevTools 能直接改组件状态，devtools 里能改任何 JS 内存，
 *    最省事的是他连前端都不用——直接 curl 你的 API。
 *
 *    挂上去只是让**测试**能表达这件事，它没有创造任何新的攻击面。
 *
 *    生产构建仍然不挂，理由不是安全，是**没必要**：
 *    一个只有测试用的全局变量留在生产包里，
 *    下一个人看到会去猜它是干什么的。
 */
if (import.meta.env.VITE_EXPOSE_AUTH_STORE === '1') {
  ;(window as unknown as Record<string, unknown>).__AUTH_STORE__ = useAuthStore
}
