import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/auth/store'

/**
 * ⚠️ 用的是 **classic** `createRouter`，不是 `vue-router/auto`（V-ADR-013）。
 *
 *    Vue Router 5 把 unplugin-vue-router 收进了主包，文件式路由是官方推荐方向。
 *    本项目**明确不用**，因为它与架构根本冲突：
 *
 *      文件式路由的真相源是**文件系统**（构建期确定）
 *      本项目的真相源是**后端数据库**（运行期下发，F-ADR-008）
 *
 *    最硬的证据是 Vue Router 5 自己的类型定义——为文件式路由设计的
 *    experimental router 里写着：
 *
 *      > This router does not have `addRoute()` and `removeRoute()` methods
 *      > and is meant to be used with file-based routing.
 *
 *    **它直接删掉了动态路由 API。** 不是巧合——
 *    文件式路由和动态注册是互斥的两种世界观。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/pages/Login.vue') },
    { path: '/', component: () => import('@/pages/Home.vue') },
    // vue-v0.3.0 加布局与嵌套路由，vue-v0.5.0 改成动态注册
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

/**
 * 🔴 最小认证守卫：**只管「登没登录」，刻意不管权限。**
 *
 * 权限判断 + profile 预加载 + 动态路由注册是 vue-v0.5.0 的 guard.ts，
 * 会把这一段整个重写。两者职责分开，否则以后改一个会意外影响另一个。
 *
 * 📌 **这是本阶段一条暗线的起点：同一个职责，React 放在组件树里，Vue 放在导航流程里。**
 *
 *    React 版 fe-v0.3.0 用的是组件：
 *        <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
 *
 *    差异从这里就开始，到 vue-v0.5.0 完全展开（V-ADR-005）。
 *
 * ⚠️ 本 tag 刻意**不处理** status === 'unknown'：
 *    profile 预加载还在 App.vue 里（对应 React 的 useBootstrapAuth），
 *    unknown 时直接放行，由页面自己显示 loading。
 *    在守卫里 await profile 是 vue-v0.5.0 的事——那一步还会带出
 *    「addRoute 之后必须重新导航」这个陷阱。
 */
router.beforeEach((to) => {
  if (to.path === '/login') return true

  // ⚠️ useAuthStore() 写在**回调内部**。
  //    提到模块顶层会抛 getActivePinia() was called with no active Pinia ——
  //    本文件在 main.ts 里被 import，那时 app.use(pinia) 还没执行（V-ADR-003）。
  const auth = useAuthStore()
  if (auth.status === 'anonymous') {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
