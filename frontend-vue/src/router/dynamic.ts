import { watch } from 'vue'
import type { Router } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import type { MenuNode } from '@/types/auth'

import { buildRoutes } from './buildRoutes'

/**
 * 🔴 动态路由的注册与**清理**（V-ADR-004）。
 *
 * ⚠️⚠️ **这个文件在 React 版里不存在。**
 *
 *    React 的做法是「用 menus 重新构造整棵路由表」：
 *
 *        const routes = useMemo(() => buildRoutes(menus), [fingerprint])
 *        <Routes>{routes.map(r => <Route ... />)}</Routes>
 *
 *    路由表是**渲染的产物**，是 `f(menus)`。menus 变了就重新算一遍，
 *    **旧路由自动消失，不需要写任何清理代码**。
 *
 *    Vue Router 只有 `addRoute()`，**没有 `setRoutes()`**。
 *    路由表是 router 实例上的**可变状态**，只能往里加。
 *    于是多出两笔债：
 *
 *      1. 加完之后当前导航不会重新匹配 → 刷新变 404（见 guard.ts）
 *      2. 登出/换账号后旧路由**还在**（VE-3.8）
 *
 * 📌 **关于第 2 条，实测纠正了规格书里的一个错误预言：**
 *
 *    V-ADR-004 / VE-3.8 / 04 对比文档第 6 节都写着：
 *      「换个权限更小的账号，上个账号的路由还在 → **进得去但一片空白** →
 *        用户以为系统坏了」
 *
 *    **这没有发生。** 关掉全部清理逻辑后实测：
 *
 *      登出后        路由表里 /system/users 等**确实还在**（残留是真的）
 *      cs_staff 登录  /tickets 甚至被注册了**两次**
 *      但 push('/system/users') → **仍然 403**
 *
 *    因为守卫**每次导航**都查 `to.meta.perm`，而残留路由带的是
 *    **上一个用户的** permCode，新用户没有它 → 403。
 *
 *    那个预言隐含了一个假设：「守卫只在注册时判断一次」。
 *    实际不是——所以残留被第二道拦住了。React 版有同样的第二道
 *    （`<PermissionGate perm={node.permCode}>`）。
 *
 * ⚠️ **但清理仍然必须做**，理由要换成真的：
 *
 *      1. **重复注册会无限增长**——每次权限变更、每次换账号都叠一层
 *      2. **路由表泄露上一个用户能进哪些页面**（不构成越权，属不必要暴露）
 *      3. 两个用户的同一 `routePath` 若映射到不同 `component`，
 *         匹配结果**不确定**
 *
 *    > 教训不是「预言错了」，而是：**「这个 bug 会造成什么后果」和
 *    > 「这个 bug 存在」是两件事。** 我把前者写死在文档里，
 *    > 而它依赖另一层的行为——那一层恰好也做了防护。
 */

/** `addRoute` 的返回值就是「移除这条路由」的函数。 */
let registered: Array<() => void> = []

/**
 * 🔴📌 把「注册动态路由」变成 `menus` 的**派生效果**（实测才想清楚的设计）。
 *
 * ⚠️ **第一版是「守卫里显式调 registerDynamicRoutes」，它有 bug：**
 *
 *    守卫只在 `status === 'unknown'` 分支里注册。而**登录**时
 *    status 是从 `anonymous` **直接跳到** `authenticated` 的，
 *    根本不经过那个分支 → 路由没注册 → 跳 `/tickets` 匹配不到
 *    → 落到兜底 → knownRoutes 里有它 → **403**。
 *
 *    表现是「登录成功，然后被自己的前端拒之门外」。
 *
 * 📌 **根因是两种模型的差异，而不是我漏写了一个调用：**
 *
 *    | | React | Vue（第一版） |
 *    | 路由表是什么 | `f(menus)`，**派生值** | 一个需要被执行的**动作** |
 *    | menus 变了 | 自动重算，路由自动在 | 得有人记得去调注册函数 |
 *    | 有几个「profile 到手」的时机 | 不关心 | **两个**（引导、登录），漏一个就出 bug |
 *
 *    → 修法不是「补上第二个调用点」，而是**把它变回派生值**：
 *      watch menus，变了就重新注册。这样「有几个入口」不再重要。
 *
 * ⚠️ `flush: 'sync'` 不能少。
 *    默认的 `'pre'` 会把回调推到下一个 tick，而守卫在 `await profile` 之后
 *    **紧接着**就 `return { ...to }` 重新导航——那时路由还没注册上，
 *    又会掉回 404/403。menus 变化极低频，sync 的开销可以忽略。
 */
export function installDynamicRoutes(router: Router) {
  const auth = useAuthStore()
  watch(
    () => auth.menus,
    (menus) => {
      if (menus.length === 0) clearDynamicRoutes()
      else registerDynamicRoutes(router, menus)
    },
    { flush: 'sync' },
  )
}

export function registerDynamicRoutes(router: Router, menus: MenuNode[]) {
  // ⚠️ 先清再加。不清的话，权限变更后重新注册会**叠加**同名路径，
  //    Vue Router 会用最后注册的那条——恰好能工作，但 registered 数组
  //    会无限增长，而且 clearDynamicRoutes 之后仍有残留。
  clearDynamicRoutes()

  for (const record of buildRoutes(menus)) {
    // ⚠️ 挂在 'layout' 下面，所以这些页面天然有侧边栏和顶栏。
    registered.push(router.addRoute('layout', record))
  }
}

export function clearDynamicRoutes() {
  /*
   * 🔴 登出、换账号后**必须**调。
   *
   * ⚠️ 为什么用 addRoute 的返回值而不是 removeRoute(name)：
   *
   *    removeRoute(name) 要求每条路由有唯一 name。菜单是后端下发的，
   *    name 只能由 routePath 派生——**两个菜单指向同一组件时会撞名**，
   *    而撞名的表现是「移除了不该移除的那条」，极难排查。
   *
   *    addRoute 的返回值不依赖 name，是**精确的**。
   */
  registered.forEach((remove) => remove())
  registered = []
}

/** 仅供测试与自检：当前注册了几条动态路由。 */
export function dynamicRouteCount() {
  return registered.length
}
