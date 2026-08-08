import { createRouter, createWebHistory } from 'vue-router'

import { installGuard } from './guard'

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
       * ⚠️ `name: 'layout'` 是 `router.addRoute('layout', record)` 的落点。
       *
       *    🟡 这是 Vue 与 React 的一处结构差异：
       *       React Router 的动态路由是「重新构造整棵路由树」，
       *       父子关系由 JSX 嵌套表达，**不需要给节点起名**；
       *       Vue Router 的 addRoute 是「往某个已有节点下面挂」，
       *       **必须能指名道姓地找到那个父节点**。
       */
      name: 'layout',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        /*
         * ⚠️ vue-v0.5.0 起，业务页面的路由**全部由 profile 动态注册**
         *    （dynamic.ts）。这里只留三类静态路由：
         *
         *      1. 首页重定向
         *      2. 不在菜单里的页面（详情页）—— 对应 React 版的 STATIC_ROUTES
         *      3. 403 / 404 兜底
         *
         *    🔴 name: 'home' 不能省。父路由有 name 而空路径子路由没有时，
         *       导航到 '/' 会命中**父路由的 name**，空路径子路由不会被渲染——
         *       表现是「登录成功了，但页面停在原地」（vue-v0.3.0 踩过）。
         */
        { path: '', name: 'home', component: () => import('@/pages/HomeRedirect.vue') },

        // 详情页不在菜单里，所以不会被动态注册，只能静态声明（F-ADR-007）。
        // 它没有 meta.perm —— 权限由后端的 .for_user() 决定（范围外 404）。
        { path: 'tickets/:id', component: () => import('@/pages/tickets/Detail.vue') },

        { path: '403', component: () => import('@/pages/Forbidden.vue') },
        {
          path: ':pathMatch(.*)*',
          component: () => import('@/pages/NotFound.vue'),
          // ⚠️ 标记出来，让守卫知道「这是兜底」而不是一条真路由，
          //    从而去 knownRoutes 里查该给 403 还是 404。
          meta: { notFound: true },
        },
      ],
    },
  ],
})

installGuard(router)

export default router
