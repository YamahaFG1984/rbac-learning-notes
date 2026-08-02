import { lazy, Suspense } from 'react'

import { Spin } from 'antd'
import type { RouteObject } from 'react-router'

import { PERM } from '@/constants/permissions'

import { PermissionGate } from './PermissionGate'

const TicketDetail = lazy(() => import('@/pages/tickets/Detail'))

/**
 * 不在菜单里的页面。
 *
 * 详情页、编辑页这类「从列表点进去」的路由不属于菜单树，
 * 后端的 menus 里没有它们——但它们同样需要权限判断。
 *
 * **这正是「动态注册 + 守卫兜底」双管齐下的理由**（F-ADR-007）：
 *   · 只动态注册 → 这些页面根本没有路由
 *   · 只用守卫   → 所有页面组件都进 bundle，系统结构完全暴露
 *
 * ⚠️ 这里的权限码是**手工**与后端对齐的。类型是 PermCode，
 *    写错会编译报错；但「写成了另一个存在的码」它管不了——
 *    那要靠 fe-v0.15.0 的前后端对账测试。
 */
export const STATIC_ROUTES: RouteObject[] = [
  {
    path: 'tickets/:id',
    element: (
      <PermissionGate perm={PERM.TICKET_TICKET_VIEW}>
        <Suspense fallback={<Spin style={{ margin: 48 }} />}>
          <TicketDetail />
        </Suspense>
      </PermissionGate>
    ),
  },
]
