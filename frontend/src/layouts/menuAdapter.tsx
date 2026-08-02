import type { MenuProps } from 'antd'
import { createElement } from 'react'

import type { MenuNode } from '@/types/auth'

import { resolveIcon } from './iconMap'

type AntdMenuItems = NonNullable<MenuProps['items']>

/**
 * 目录节点没有 routePath，但 AntD 的 Menu 要求每个节点有唯一 key。
 * 用 id 造一个不可能和真实路由撞车的 key。
 */
function keyOf(node: MenuNode): string {
  return node.routePath ?? `catalog-${node.id}`
}

/**
 * MenuNode[] → AntD `Menu` 的 items。
 *
 * ⚠️ 这里**不做任何权限判断**。
 *
 *    后端 get_user_menu_tree()（v0.11.0）已经做完了全部过滤：
 *    自底向上标记有权限的菜单、向上保留祖先目录、空目录自动消失。
 *
 *    前端再过滤一遍的后果不是「多此一举」，是**两套逻辑必然漂移**——
 *    后端改了「空目录是否显示」的判定，前端不会知道。
 *    这是 F-ADR-015「前端不做二次过滤」在菜单上的形态。
 *
 * ⚠️ 写成纯函数而不是内联在组件里，是为了 fe-v0.15.0 能零 mock 单测：
 *    输入一棵树，断言输出结构。
 */
export function toAntdMenuItems(menus: MenuNode[]): AntdMenuItems {
  return menus.map((node) => {
    const base = {
      key: keyOf(node),
      icon: createElement(resolveIcon(node.icon)),
      label: node.name,
    }
    return node.children.length > 0
      ? { ...base, children: toAntdMenuItems(node.children) }
      : base
  })
}

/** 深度优先展平，同时记录每个节点的祖先 key 链。 */
function flatten(
  menus: MenuNode[],
  ancestors: string[] = [],
): Array<{ node: MenuNode; ancestors: string[] }> {
  const out: Array<{ node: MenuNode; ancestors: string[] }> = []
  for (const node of menus) {
    out.push({ node, ancestors })
    if (node.children.length > 0) {
      out.push(...flatten(node.children, [...ancestors, keyOf(node)]))
    }
  }
  return out
}

/**
 * 算出当前路径对应的选中项和需要展开的父目录。
 *
 * ⚠️ 为什么不能直接 `selectedKeys={[pathname]}`：
 *    在 /tickets/42（详情页）时 pathname 不等于任何菜单 key，
 *    侧边栏会变成「什么都没选中」，用户会觉得自己不在任何菜单里。
 *    所以要做**前缀匹配**，取最长的那个。
 *
 * ⚠️ 前缀匹配必须带分隔符：`startsWith(routePath + '/')`。
 *    不加斜杠的话 /tickets-archive 会被误判为 /tickets 的子路径。
 *
 *    ——这是同一个坑第三次出现（部门树 path 尾斜杠 v0.3.0、
 *      ORDER BY path 排序 bug v0.4.0、这里）。
 *      规则：**用字符串前缀表达树/路径的包含关系时，永远带上分隔符。**
 */
export function findActiveKeys(
  menus: MenuNode[],
  pathname: string,
): { selectedKeys: string[]; openKeys: string[] } {
  const candidates = flatten(menus).filter((e) => e.node.routePath)

  const matched = candidates
    .filter(({ node }) => {
      const p = node.routePath!
      return pathname === p || pathname.startsWith(p + '/')
    })
    .sort((a, b) => b.node.routePath!.length - a.node.routePath!.length)[0]

  if (!matched) return { selectedKeys: [], openKeys: [] }
  return {
    selectedKeys: [matched.node.routePath!],
    openKeys: matched.ancestors,
  }
}
