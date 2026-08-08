import { createRouter, createWebHistory } from 'vue-router'

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
export default createRouter({
  history: createWebHistory(),
  routes: [
    // vue-v0.1.0 只有一个占位页。
    // 布局与嵌套路由在 vue-v0.3.0，动态注册在 vue-v0.5.0。
    { path: '/', component: () => import('@/pages/Home.vue') },
  ],
})
