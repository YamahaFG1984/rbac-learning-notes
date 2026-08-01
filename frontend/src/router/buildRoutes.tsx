import { Suspense } from 'react'

import { Spin } from 'antd'
import type { RouteObject } from 'react-router'

import type { PermCode } from '@/constants/permissions'
import type { MenuNode } from '@/types/auth'

import { PermissionGate } from './PermissionGate'
import { resolveComponent } from './registry'

function MisconfiguredPage({ component }: { component: string | null }) {
  return (
    <div style={{ padding: 24, color: '#cf1322' }}>
      页面组件未找到：<code>{component}</code>
      <div style={{ color: '#8c8c8c', marginTop: 8, fontSize: 12 }}>
        后端权限点的 component 字段配置有误。用
        <code> python manage.py sync_permissions --check-frontend </code>
        排查。
      </div>
    </div>
  )
}

/** 把后端下发的菜单树摊平成路由表。catalog 节点本身不产生路由。 */
export function buildRoutes(menus: MenuNode[]): RouteObject[] {
  const routes: RouteObject[] = []

  const walk = (nodes: MenuNode[]) => {
    for (const node of nodes) {
      if (node.routePath && node.component) {
        const Component = resolveComponent(node.component)
        routes.push({
          path: node.routePath.replace(/^\//, ''),
          element: (
            // 守卫是**兜底**不是主力：能走到这里说明后端已经把这个菜单
            // 下发给了当前用户，所以正常情况下必然通过。
            // 但静态注册的路由、或将来漏注册的情况，还有这一道。
            <PermissionGate perm={(node.permCode ?? null) as PermCode | null}>
              <Suspense fallback={<Spin style={{ margin: 48 }} />}>
                {Component ? <Component /> : <MisconfiguredPage component={node.component} />}
              </Suspense>
            </PermissionGate>
          ),
        })
      }
      walk(node.children)
    }
  }

  walk(menus)
  return routes
}
