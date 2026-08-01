import { describe, expect, it } from 'vitest'

import { findActiveKeys, toAntdMenuItems } from '@/layouts/menuAdapter'
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

const MENUS: MenuNode[] = [
  node({
    id: 1,
    name: '工单管理',
    icon: 'ticket',
    perm_type: 'catalog',
    children: [
      node({ id: 2, name: '工单列表', icon: 'FileText', routePath: '/tickets' }),
      // 故意造一个前缀相同的兄弟节点，用来抓「前缀匹配不带分隔符」的 bug
      node({ id: 3, name: '工单归档', routePath: '/tickets-archive' }),
    ],
  }),
  node({
    id: 4,
    name: '系统管理',
    perm_type: 'catalog',
    children: [
      node({ id: 5, name: '用户管理', icon: 'Team', routePath: '/system/users' }),
    ],
  }),
]

describe('toAntdMenuItems', () => {
  it('目录 → 带 children 的项，叶子 → 普通项', () => {
    const items = toAntdMenuItems(MENUS)
    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ key: 'catalog-1', label: '工单管理' })
    expect(items[0]).toHaveProperty('children')
    expect(items[1]).toMatchObject({ key: 'catalog-4' })
  })

  it('叶子节点用 routePath 做 key —— 点击时才能直接拿去 navigate', () => {
    const items = toAntdMenuItems(MENUS)
    const children = (items[0] as { children: Array<{ key: string }> }).children
    expect(children.map((c) => c.key)).toEqual(['/tickets', '/tickets-archive'])
  })

  it('图标名不认识时降级为默认图标，而不是抛错', () => {
    // 后端把 icon 写成了一个前端没有的名字
    const bad = [node({ id: 9, name: '未知', icon: 'NoSuchIconName' })]
    expect(() => toAntdMenuItems(bad)).not.toThrow()
    expect(toAntdMenuItems(bad)[0]).toHaveProperty('icon')
  })

  it('不做任何权限过滤 —— 给什么渲染什么（过滤是后端的职责）', () => {
    // 一个 permCode 为 null 的节点也照样渲染出来
    const items = toAntdMenuItems([node({ id: 7, permCode: null })])
    expect(items).toHaveLength(1)
  })
})

describe('findActiveKeys', () => {
  it('精确匹配', () => {
    expect(findActiveKeys(MENUS, '/tickets').selectedKeys).toEqual(['/tickets'])
  })

  it('详情页高亮父级列表菜单，并展开其所在目录', () => {
    const { selectedKeys, openKeys } = findActiveKeys(MENUS, '/tickets/42')
    expect(selectedKeys).toEqual(['/tickets'])
    expect(openKeys).toEqual(['catalog-1'])
  })

  it('🔴 /tickets-archive 不能被误判为 /tickets 的子路径', () => {
    // 前缀匹配不带 '/' 的话，这里会错误地高亮「工单列表」。
    // 同一个坑第三次出现：部门树 path 尾斜杠、ORDER BY path、菜单高亮。
    expect(findActiveKeys(MENUS, '/tickets-archive').selectedKeys).toEqual([
      '/tickets-archive',
    ])
  })

  it('多个候选时取最长匹配', () => {
    const menus = [
      node({ id: 1, routePath: '/system' }),
      node({ id: 2, routePath: '/system/users' }),
    ]
    expect(findActiveKeys(menus, '/system/users/3').selectedKeys).toEqual([
      '/system/users',
    ])
  })

  it('匹配不到时返回空数组，而不是 undefined', () => {
    expect(findActiveKeys(MENUS, '/nowhere')).toEqual({
      selectedKeys: [],
      openKeys: [],
    })
  })

  it('空菜单（no_role 用户）不炸', () => {
    expect(findActiveKeys([], '/tickets').selectedKeys).toEqual([])
  })
})
