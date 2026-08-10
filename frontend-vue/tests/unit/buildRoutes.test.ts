import { describe, expect, it } from 'vitest'

import { buildRoutes } from '@/router/buildRoutes'
import { SUPERADMIN_PROFILE } from '@/test/fixtures'
import type { MenuNode } from '@/types/auth'

const node = (o: Partial<MenuNode> & { id: number }): MenuNode => ({
  name: 'x', icon: '', url: null, routePath: null, component: null,
  permCode: null, perm_type: 'menu', children: [], ...o,
})

describe('buildRoutes —— 菜单树 → 路由记录', () => {
  it('每个有 routePath+component 的节点产生一条路由', () => {
    const routes = buildRoutes(SUPERADMIN_PROFILE.menus)
    expect(routes.length).toBeGreaterThan(0)
    expect(routes.every((r) => typeof r.path === 'string')).toBe(true)
  })

  it('🔴 catalog 节点本身不产生路由，但会递归它的子节点', () => {
    const tree = [
      node({ id: 1, perm_type: 'catalog', children: [
        node({ id: 2, routePath: '/a', component: 'tickets/List', permCode: 'a:b:c' }),
      ]}),
    ]
    const routes = buildRoutes(tree)
    expect(routes).toHaveLength(1)
    expect(routes[0].path).toBe('a')
  })

  it('🔴 去掉前导斜杠 —— 它是挂在 layout 下的**子路由**', () => {
    // 带斜杠会被当成绝对路径注册到根上，导致布局不生效
    const routes = buildRoutes([
      node({ id: 1, routePath: '/system/users', component: 'system/Users', permCode: 'a:b:c' }),
    ])
    expect(routes[0].path).toBe('system/users')
  })

  it('permCode 写进 meta，供守卫兜底判断', () => {
    const routes = buildRoutes([
      node({ id: 1, routePath: '/a', component: 'tickets/List', permCode: 'ticket:ticket:view' }),
    ])
    expect(routes[0].meta?.perm).toBe('ticket:ticket:view')
  })

  it('component 配错时降级成提示页，**不抛异常**', () => {
    // 一个配错的字符串不该让整个应用白屏（同后端对 NoReverseMatch 的处理）
    expect(() =>
      buildRoutes([node({ id: 1, routePath: '/a', component: '不存在/的组件', permCode: 'a:b:c' })]),
    ).not.toThrow()
  })

  it('只有 routePath 没有 component 的节点被跳过', () => {
    expect(buildRoutes([node({ id: 1, routePath: '/a' })])).toHaveLength(0)
  })
})
