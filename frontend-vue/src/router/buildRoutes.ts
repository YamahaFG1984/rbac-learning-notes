import type { RouteRecordRaw } from 'vue-router'

import MisconfiguredPage from '@/components/MisconfiguredPage.vue'
import type { MenuNode } from '@/types/auth'

import { resolveComponent } from './registry'

/**
 * 把后端下发的菜单树摊平成路由记录。`catalog` 节点本身不产生路由。
 *
 * 🟡 与 React 版 `buildRoutes.tsx` 的差异：
 *
 *    React 在这里就把 `<PermissionGate>` 包进 element 里（守卫是**渲染树的一部分**）。
 *    Vue 只把 `permCode` 写进 `meta`，判断留给 `guard.ts`（守卫是**导航流程的一部分**）。
 *
 *    → 结果是 Vue 版的 buildRoutes **更纯粹**：它只做「树 → 路由表」这一件事，
 *      不掺权限判断。React 版则必须在这里知道守卫组件的存在。
 *
 *    ⚠️ 但别读成「Vue 更好」——代价是权限判断被挪到了另一个文件，
 *      读代码时要跳一次。React 版把「这条路由要什么权限」写在了同一个地方。
 */
export function buildRoutes(menus: MenuNode[]): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = []

  const walk = (nodes: MenuNode[]) => {
    for (const node of nodes) {
      if (node.routePath && node.component) {
        const loader = resolveComponent(node.component)
        routes.push({
          // ⚠️ 去掉前导斜杠：它是挂在 'layout'（path: '/'）下面的**子路由**。
          //    带斜杠的话会被当成绝对路径，注册到根上，导致布局不生效。
          path: node.routePath.replace(/^\//, ''),
          component: loader ?? MisconfiguredPage,
          meta: {
            // 守卫是**兜底**不是主力：能走到这里说明后端已经把这个菜单
            // 下发给了当前用户，正常情况下必然通过。
            // 但静态注册的路由、或将来漏注册的情况，还有这一道。
            perm: node.permCode,
            component: node.component,
          },
        })
      }
      walk(node.children)
    }
  }

  walk(menus)
  return routes
}
