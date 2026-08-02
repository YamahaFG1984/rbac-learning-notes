export interface Department {
  id: number
  name: string
}

export interface User {
  id: number
  username: string
  realName: string
  department: Department | null
  isSuperuser: boolean
}

export interface MenuNode {
  id: number
  name: string
  icon: string
  /** Django 模板版的路径（模板版用，SPA 忽略） */
  url: string | null
  /** SPA 的前端路由，由 API 层补上（F-ADR-008）。catalog 为 null */
  routePath: string | null
  /** 相对 src/pages/ 的组件路径，如 tickets/List */
  component: string | null
  /** 权限码，供前端路由守卫兜底判断。catalog 为 null */
  permCode: string | null
  perm_type: 'catalog' | 'menu' | 'button'
  children: MenuNode[]
}

export interface Profile {
  user: User
  /** 超管为 ['*'] —— 通配的处理只在 usePermission 里做一次（fe-v0.6.0） */
  perms: string[]
  menus: MenuNode[]
  /**
   * 系统里**全部**菜单路径（含当前用户无权限的）。
   *
   * 用来区分「路径存在但无权限」（→ 403）和「路径不存在」（→ 404）。
   * 它确实泄露了系统有哪些页面——见后端 build_profile_payload 的说明。
   */
  knownRoutes: string[]
}
