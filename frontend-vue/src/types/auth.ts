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
  /** 超管为 ['*'] —— 通配的处理只在 usePermission 里做一次（vue-v0.4.0） */
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

/*
 * 📌 与 React 版的一个时间差，值得记一笔。
 *
 *    React 的这份类型是**分两次长出来**的：
 *      fe-v0.3.0  MenuNode 只有 {id, name, icon, url, permType, children}
 *      fe-v0.5.0  才加上 routePath / component / permCode，Profile 才加 knownRoutes
 *    因为那些字段是它自己在 fe-v0.5.0 加到后端的。
 *
 *    Vue 版拿到的是**已经完成的 API 契约**，所以一步到位。
 *
 *    「两个 tag 消失了」消失的不只是工作量，还有
 *    **「类型定义分两次长出来」这个过程本身**——
 *    接第三个前端时，契约是给定的，不是协商出来的。
 */
