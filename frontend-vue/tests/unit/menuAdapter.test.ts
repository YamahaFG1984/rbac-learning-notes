import { describe, expect, it } from 'vitest'

import { findActiveKeys, toMenuItems } from '@/layouts/menuAdapter'
import { CS_MANAGER_PROFILE, SUPERADMIN_PROFILE } from '@/test/fixtures'
import type { MenuNode } from '@/types/auth'

/**
 * 🟢 `findActiveKeys` 与 React 版**逐行相同**（去掉注释后 30 行、0 处不同）。
 *    它是纯函数，与框架无关——所以这些断言也应该与 React 版一致。
 */
describe('toMenuItems', () => {
  it('把菜单树转成 antdv items', () => {
    const items = toMenuItems(SUPERADMIN_PROFILE.menus)
    expect(items.length).toBe(SUPERADMIN_PROFILE.menus.length)
    expect(items.length).toBeGreaterThan(0)
  })

  it('🔴 不做任何权限过滤（后端已经过滤完了）', () => {
    // 后端 get_user_menu_tree 已完成全部过滤：空目录不返回、无权限的不返回。
    // 前端再过滤一遍 = 两套逻辑必然漂移（V-ADR-015）
    const items = toMenuItems(CS_MANAGER_PROFILE.menus)
    expect(items.length).toBe(CS_MANAGER_PROFILE.menus.length)
  })

  it('catalog 节点用 catalog-<id> 当 key（不与真实路由撞车）', () => {
    const tree: MenuNode[] = [
      { id: 9, name: '目录', icon: '', url: null, routePath: null, component: null,
        permCode: null, perm_type: 'catalog',
        children: [{ id: 10, name: '页面', icon: '', url: null, routePath: '/x',
          component: 'x/X', permCode: 'a:b:c', perm_type: 'menu', children: [] }] },
    ]
    const items = toMenuItems(tree) as Array<{ key: string; children?: unknown[] }>
    expect(items[0].key).toBe('catalog-9')
    expect(items[0].children).toHaveLength(1)
  })

  it('🔴 icon 是**渲染函数**而不是 VNode（Vue 的 VNode 不可复用）', () => {
    const items = toMenuItems(SUPERADMIN_PROFILE.menus) as Array<{ icon: unknown }>
    expect(typeof items[0].icon).toBe('function')
  })

  it('图标名配错时不崩（降级成默认图标）', () => {
    const tree: MenuNode[] = [
      { id: 1, name: 'x', icon: '这个图标不存在', url: null, routePath: '/x',
        component: 'x/X', permCode: 'a:b:c', perm_type: 'menu', children: [] },
    ]
    expect(() => toMenuItems(tree)).not.toThrow()
  })
})

describe('findActiveKeys', () => {
  const menus = SUPERADMIN_PROFILE.menus

  it('精确匹配', () => {
    expect(findActiveKeys(menus, '/tickets').selectedKeys).toEqual(['/tickets'])
  })

  it('🔴 详情页也高亮父菜单（前缀匹配，取最长的）', () => {
    expect(findActiveKeys(menus, '/tickets/42').selectedKeys).toEqual(['/tickets'])
  })

  it('🔴🔴 前缀匹配必须带分隔符 —— /tickets-archive 不属于 /tickets', () => {
    /*
     * 同一个坑第五次出现（部门树 path 尾斜杠 v0.3.0、ORDER BY path 排序 v0.4.0、
     * React 菜单高亮 fe-v0.8.0、vue-v0.5.0 守卫的 403/404 分流、这里）。
     *
     * **规则：用字符串前缀表达树/路径的包含关系时，永远带上分隔符。**
     */
    expect(findActiveKeys(menus, '/tickets-archive').selectedKeys).toEqual([])
  })

  it('匹配不到时返回空，不抛错', () => {
    expect(findActiveKeys(menus, '/nope')).toEqual({ selectedKeys: [], openKeys: [] })
  })

  it('返回祖先 key 用于展开父目录', () => {
    const { openKeys } = findActiveKeys(menus, '/system/users')
    expect(openKeys.length).toBeGreaterThan(0)
  })
})

describe('边界情况', () => {
  it('空菜单返回空数组', () => {
    expect(toMenuItems([])).toEqual([])
    expect(findActiveKeys([], '/x')).toEqual({ selectedKeys: [], openKeys: [] })
  })

  it('icon 为 null / undefined 时用默认图标', () => {
    const tree: MenuNode[] = [
      { id: 1, name: 'x', icon: null as unknown as string, url: null, routePath: '/x',
        component: 'x/X', permCode: 'a:b:c', perm_type: 'menu', children: [] },
    ]
    const items = toMenuItems(tree) as Array<{ icon: () => unknown }>
    expect(() => items[0].icon()).not.toThrow()
  })

  it('图标大小写不敏感（后端的 icon 名大小写混乱）', () => {
    const mk = (icon: string): MenuNode[] => [
      { id: 1, name: 'x', icon, url: null, routePath: '/x', component: 'x/X',
        permCode: 'a:b:c', perm_type: 'menu', children: [] },
    ]
    const a = toMenuItems(mk('FileText')) as Array<{ icon: () => unknown }>
    const b = toMenuItems(mk('filetext')) as Array<{ icon: () => unknown }>
    // 两者应该解析到同一个组件（toLowerCase 归一）
    expect((a[0].icon() as { type: unknown }).type).toBe((b[0].icon() as { type: unknown }).type)
  })

  it('多层嵌套时 openKeys 包含全部祖先', () => {
    const tree: MenuNode[] = [
      { id: 1, name: 'A', icon: '', url: null, routePath: null, component: null,
        permCode: null, perm_type: 'catalog', children: [
        { id: 2, name: 'B', icon: '', url: null, routePath: null, component: null,
          permCode: null, perm_type: 'catalog', children: [
          { id: 3, name: 'C', icon: '', url: null, routePath: '/a/b/c',
            component: 'x/X', permCode: 'a:b:c', perm_type: 'menu', children: [] },
        ]},
      ]},
    ]
    expect(findActiveKeys(tree, '/a/b/c').openKeys).toEqual(['catalog-1', 'catalog-2'])
  })
})

describe('flatten 的祖先链（覆盖递归分支）', () => {
  it('同级多个叶子节点都能各自匹配', () => {
    const tree: MenuNode[] = [
      { id: 1, name: 'A', icon: '', url: null, routePath: null, component: null,
        permCode: null, perm_type: 'catalog', children: [
        { id: 2, name: 'B', icon: '', url: null, routePath: '/a', component: 'x/X',
          permCode: 'a:b:c', perm_type: 'menu', children: [] },
        { id: 3, name: 'C', icon: '', url: null, routePath: '/b', component: 'y/Y',
          permCode: 'd:e:f', perm_type: 'menu', children: [] },
      ]},
    ]
    expect(findActiveKeys(tree, '/a').selectedKeys).toEqual(['/a'])
    expect(findActiveKeys(tree, '/b').selectedKeys).toEqual(['/b'])
    expect(findActiveKeys(tree, '/b').openKeys).toEqual(['catalog-1'])
  })
})

describe('🔴 前缀重叠时取**最长**的那个', () => {
  it('/system 与 /system/users 同时匹配时，选中更深的那个', () => {
    /*
     * ⚠️ 这条用例覆盖的是 `.sort()` 的比较函数 —— 它**只有在两条前缀
     *    同时匹配时才会执行**，而那正是「取最长的」这条规则存在的理由。
     *
     *    没有这条用例的话：sort 的比较函数一次都不跑（覆盖率能看出来），
     *    而且把它写反（a - b 而不是 b - a）测试照样全绿。
     */
    const tree: MenuNode[] = [
      { id: 1, name: '系统', icon: '', url: null, routePath: '/system',
        component: 'x/X', permCode: 'a:b:c', perm_type: 'menu', children: [] },
      { id: 2, name: '用户', icon: '', url: null, routePath: '/system/users',
        component: 'y/Y', permCode: 'd:e:f', perm_type: 'menu', children: [] },
    ]
    expect(findActiveKeys(tree, '/system/users').selectedKeys).toEqual(['/system/users'])
    expect(findActiveKeys(tree, '/system/users/9').selectedKeys).toEqual(['/system/users'])
    expect(findActiveKeys(tree, '/system').selectedKeys).toEqual(['/system'])
  })
})
