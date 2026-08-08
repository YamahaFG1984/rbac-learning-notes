import { defineStore } from 'pinia'
import { ref } from 'vue'

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
 * ⚠️ Vue 版还有一条 React 版没有的理由（V-ADR-006）：
 *    vue-v0.5.0 的导航守卫靠 `status === 'unknown'` 判断「要不要拉 profile」。
 *    用布尔的话「没登录」和「没拉过」分不开，每次导航都会重拉一次 profile，
 *    直接违反 VNFR-7。
 *
 * ⚠️ setProfile 是权限数据的**唯一写入口**（F-ADR-005 / V-ADR-003）。
 *    从 vue-v0.4.0 起只允许 useProfileQuery 调用它。
 *    两处写入 = 两个真相源，很快就会不一致。
 *
 *    🔴 这条规则在 Pinia 下**比 Zustand 更难守**：
 *       Pinia 的 state 是公开可写的（`auth.perms = [...]` 完全合法、不报错），
 *       而 Zustand 至少还要走一次 `setState`。
 *       vue-v0.13.0 会加一条结构性测试扫这类直接赋值。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const perms = ref<string[]>([])
  const menus = ref<MenuNode[]>([])
  const knownRoutes = ref<string[]>([])
  const status = ref<'unknown' | 'authenticated' | 'anonymous'>('unknown')

  function setProfile(profile: Profile) {
    user.value = profile.user
    perms.value = profile.perms
    menus.value = profile.menus
    knownRoutes.value = profile.knownRoutes
    status.value = 'authenticated'
  }

  function reset() {
    user.value = null
    perms.value = []
    menus.value = []
    knownRoutes.value = []
    // ⚠️ 终态，**不是** 'unknown'。
    //    留在 unknown 会让 vue-v0.5.0 的守卫无限重定向
    //    （Maximum recursive navigation guard calls）。
    status.value = 'anonymous'
  }

  return { user, perms, menus, knownRoutes, status, setProfile, reset }
})

/*
 * 📌 对照 React 版 store.ts 的结尾：那里有一段
 *
 *      if (import.meta.env.VITE_EXPOSE_AUTH_STORE === '1') {
 *        window.__AUTH_STORE__ = useAuthStore
 *      }
 *
 *    外加一整段注释解释「这不是为了测试而降低安全」——
 *    因为 fe-v0.16.0 的「篡改权限」测试需要一个入口。
 *
 *    **Vue 版不需要这段。** Pinia 的 state 本来就是可写的响应式对象，
 *    Devtools 里点两下就改了，E2E 里通过 app.config.globalProperties.$pinia 就能拿到。
 *
 *    这不是 Vue 的安全缺陷——两边的实际暴露程度**完全一样**
 *    （React DevTools 同样能改任何组件状态，攻击者同样可以完全不用你的前端）。
 *    Vue 只是把「前端状态从来就不是秘密」这件事表达得更诚实，
 *    让那段解释变得多余。见 04 对比文档第 15 节。
 */
