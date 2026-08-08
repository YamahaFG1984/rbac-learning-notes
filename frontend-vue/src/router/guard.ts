import type { Router } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import { fetchProfileIntoStore } from '@/auth/useProfileQuery'
import type { PermCode } from '@/constants/permissions'
import { useUiStore } from '@/store/uiStore'


/**
 * ⚠️⚠️ **这不是安全边界。**
 *
 *    `auth.can()` 读的是用户浏览器内存里的 Pinia store，
 *    Vue Devtools 里改成 `['*']` 只需要几秒；
 *    而且攻击者根本不必用这个前端——他可以直接 curl 你的 API。
 *
 *    模板版：「攻击者不点你的按钮，他直接发请求。」
 *    SPA 版：「攻击者不用你的路由，甚至不用你的前端。」
 *
 * 🔴 **Vue 的守卫比 React 的更容易造成错觉。**
 *
 *    它拦在**导航期**，页面组件根本不会被创建、网络请求也不会发出，
 *    写出来还特别像鉴权：
 *
 *        if (!auth.can(to.meta.perm)) return { path: '/403' }
 *
 *    **正因为它更像，错觉更强。拦得早 ≠ 拦得住。**
 *    唯一决定安全的是「拦在哪一侧」，不是「拦在哪一步」。
 *
 *    唯一的安全边界是后端的 `HasPerm` + `ScopedQuerysetMixin`。
 *    vue-v0.14.0 会用与 React 版**逐字相同**的 E2E 证明这一点。
 *
 * 那它有什么用？它挡的不是攻击者，是**误操作和坏链接**——
 * 用户点到一个进去必然报错的页面，体验很差。仅此而已。
 */

/** 不需要登录也能访问的路径。 */
const PUBLIC_PATHS = new Set(['/login'])

export function installGuard(router: Router) {
  router.beforeEach(async (to) => {
    if (PUBLIC_PATHS.has(to.path)) return true

    const auth = useAuthStore()

    // ── 1. profile 还没拉过 → 先拉 ────────────────────────────────
    //
    // 这是 FE-2.3「加载完成前不渲染业务界面」在 Vue 里的形态：
    // 不是「不渲染」，而是**「不放行」**。
    if (auth.status === 'unknown') {
      try {
        await fetchProfileIntoStore()
      } catch {
        // ⚠️ fetchProfileIntoStore 保证无论成败都把 status 置为终态。
        //    留在 unknown 的话下一行的重新导航会无限循环。
        return { path: '/login', query: { redirect: to.fullPath } }
      }

      // ⚠️ 这里**不再显式注册**——setProfile 写 menus 时，
      //    installDynamicRoutes 的 sync watcher 已经把路由加好了。

      /*
       * 🔴🔴 **本 tag 的核心，也是最不直观的一行。**
       *
       *    addRoute() 之后，参数 `to` 是**在旧路由表上算出来的**
       *    （大概率已经落到 404 兜底路由）。直接 return true 会渲染那个 404 ——
       *    这正是 F-ADR-007 描述的「刷新页面变 404」在 Vue 里的表现形式。
       *
       *    必须重新发起一次导航，让它在**新**路由表上重新匹配。
       *    replace: true 是为了不在历史里留下一条 404。
       *
       *    ⚠️ 它看起来像死循环（「导航到我自己刚才要去的地方」）。
       *       它不循环，是因为第二次进来时 auth.status 已经不是 'unknown' 了——
       *       **这个保证藏在另一个变量里，是整段代码最脆弱的地方。**
       */
      return { ...to, replace: true }
    }

    // ── 2. 未登录 → 送去登录页 ────────────────────────────────────
    if (auth.status === 'anonymous') {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    // ── 3. 权限判断（体验层，不是安全边界）─────────────────────────
    const perm = to.meta.perm as PermCode | null | undefined
    if (perm && !auth.can(perm)) return { path: '/403' }

    // ── 4. 匹配不到任何路由：区分 403 与 404 ──────────────────────
    //
    // ⚠️ 动态注册的副作用是**两者都匹配不到路由**，默认都会掉进兜底。
    //    如果一律返回 404，用户会以为「链接失效了」而不是「我没权限」，
    //    然后去问 IT 为什么链接坏了。
    //
    //    knownRoutes 是后端下发的**全部**菜单路径（含无权限的）。
    if (to.matched.length === 0 || to.meta.notFound === true) {
      const known = auth.knownRoutes.some(
        // ⚠️ 加 '/' —— 不加的话 /tickets-archive 会被误判为 /tickets 的子路径。
        //    同一个坑第五次出现（部门树 path、ORDER BY path、菜单高亮、这里）。
        //    **字符串前缀匹配必须带分隔符。**
        (r) => to.path === r || to.path.startsWith(r + '/'),
      )
      if (known) return { path: '/403' }
    }

    return true
  })

  // 全局 loading。⚠️ onError 分支不能漏——
  // 漏掉的表现是「导航失败后 spinner 永远转」。
  router.beforeEach(() => {
    useUiStore().navigating = true
    return true
  })
  router.afterEach(() => {
    useUiStore().navigating = false
  })
  router.onError(() => {
    useUiStore().navigating = false
  })
}
