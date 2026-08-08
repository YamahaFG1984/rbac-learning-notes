import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import { useUiStore } from '@/store/uiStore'

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
    {
      path: '/',
      /*
       * ⚠️ `name: 'layout'` 现在还没人用，但 vue-v0.5.0 的
       *    `router.addRoute('layout', record)` 要靠它找父节点。
       *
       *    🟡 这是 Vue 与 React 的一处结构差异：
       *       React Router 的动态路由是「重新构造整棵路由树」，
       *       父子关系由 JSX 嵌套表达，不需要给节点起名；
       *       Vue Router 的 addRoute 是「往某个已有节点下面挂」，
       *       **必须能指名道姓地找到那个父节点**。
       */
      name: 'layout',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        // ⚠️ vue-v0.3.0：子路由**写死**，和 Sidebar 里的 STATIC_ITEMS 一样。
        //    vue-v0.5.0 会删掉这一段，改成 profile 到手后 addRoute 动态注册。
        //
        // 🔴 `name: 'home'` 不能省。父路由有 name 而空路径子路由没有时，
        //    导航到 '/' 会命中**父路由的 name**，空路径子路由不会被渲染——
        //    表现是「登录成功了，但页面停在原地」。
        //    Vue Router 5 会打一条 VUE_ROUTER_R0103 警告说明这件事，
        //    但它只是 console.warn，**不会让任何东西失败**，很容易被忽略。
        //
        //    ⚠️ 这个坑是 Vue 特有的：React Router 的 index 路由不需要名字，
        //       因为它的路由匹配不依赖「命名节点」这个概念。
        //       而 Vue 版之所以必须给父路由起名，是为了 vue-v0.5.0 的
        //       addRoute('layout', ...) —— **一个为将来准备的名字，
        //       在当下制造了一个 bug。**
        { path: '', name: 'home', redirect: '/tickets' },
        { path: 'tickets', component: () => import('@/pages/tickets/List.vue') },
        { path: 'tickets/:id', component: () => import('@/pages/tickets/Detail.vue') },
        { path: 'system/depts', component: () => import('@/pages/system/Departments.vue') },
        { path: 'system/users', component: () => import('@/pages/system/Users.vue') },
        { path: 'system/roles', component: () => import('@/pages/system/Roles.vue') },
        { path: 'system/perms', component: () => import('@/pages/system/Permissions.vue') },
        { path: 'monitor/audit', component: () => import('@/pages/monitor/AuditLogs.vue') },
        { path: '403', component: () => import('@/pages/Forbidden.vue') },
        /*
         * ⚠️ 兜底路由的语法很容易写错（少一个 `*`、少括号）。
         *    写错的表现是**404 页面永远不出现**，所有未匹配路径白屏。
         *
         *    🟡 React Router 只要 `path="*"`。这是 Vue Router 更啰嗦的一处，
         *       代价换来的是「能给通配段起名并取到值」。
         */
        { path: ':pathMatch(.*)*', component: () => import('@/pages/NotFound.vue') },
      ],
    },
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
 *    React 版 fe-v0.4.0 用的是组件：
 *        <Route path="/" element={<RequireAuth><AdminLayout /></RequireAuth>}>
 *
 *    差异从这里就开始，到 vue-v0.5.0 完全展开（V-ADR-005）。
 *
 * ⚠️ 本 tag 刻意**不处理** status === 'unknown'：
 *    profile 预加载还在 App.vue 里（对应 React 的 useBootstrapAuth），
 *    unknown 时直接放行，由 AdminLayout 的 Spin 顶着。
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

export default router
