import { describe, expect, it } from 'vitest'

import { buildRoutes } from '@/router/buildRoutes'
import type { MenuNode } from '@/types/auth'

function node(partial: Partial<MenuNode> & { id: number }): MenuNode {
  return {
    name: `节点${partial.id}`,
    icon: '',
    url: null,
    routePath: null,
    component: null,
    permCode: null,
    perm_type: 'menu',
    children: [],
    ...partial,
  }
}

describe('buildRoutes', () => {
  it('catalog 节点本身不产生路由，只递归它的子节点', () => {
    const menus = [
      node({
        id: 1,
        perm_type: 'catalog',
        children: [
          node({
            id: 2,
            routePath: '/tickets',
            component: 'tickets/List',
            permCode: 'ticket:ticket:view',
          }),
        ],
      }),
    ]
    const routes = buildRoutes(menus)
    expect(routes).toHaveLength(1)
    expect(routes[0].path).toBe('tickets')
  })

  it('⚠️ path 去掉前导斜杠 —— 它们是嵌套在 "/" 之下的子路由', () => {
    // 带 '/' 的话 react-router 会把它当成绝对路径，
    // 于是这些页面渲染时不再套 AdminLayout（侧边栏整个消失）
    const routes = buildRoutes([
      node({ id: 1, routePath: '/system/users', component: 'system/Users' }),
    ])
    expect(routes[0].path).toBe('system/users')
  })

  it('缺 component 的节点不产生路由', () => {
    // 后端的 catalog 就是这种：有名字没组件
    const routes = buildRoutes([node({ id: 1, routePath: '/x', component: null })])
    expect(routes).toEqual([])
  })

  it('缺 routePath 的节点不产生路由', () => {
    const routes = buildRoutes([node({ id: 1, routePath: null, component: 'a/B' })])
    expect(routes).toEqual([])
  })

  it('component 指向不存在的文件时不抛错（降级为提示页）', () => {
    // 后端配错了 component 不该让整个应用崩 ——
    // 同后端 v0.11.0 对 NoReverseMatch 的处理
    expect(() =>
      buildRoutes([
        node({ id: 1, routePath: '/x', component: 'no/Such/Component' }),
      ]),
    ).not.toThrow()
  })

  it('深层嵌套全部展平', () => {
    const menus = [
      node({
        id: 1,
        perm_type: 'catalog',
        children: [
          node({
            id: 2,
            perm_type: 'catalog',
            children: [
              node({ id: 3, routePath: '/a', component: 'tickets/List' }),
              node({ id: 4, routePath: '/b', component: 'tickets/List' }),
            ],
          }),
        ],
      }),
    ]
    expect(buildRoutes(menus).map((r) => r.path)).toEqual(['a', 'b'])
  })

  it('空菜单（no_role 用户）返回空数组，不抛错', () => {
    expect(buildRoutes([])).toEqual([])
  })
})
