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
  url: string | null
  permType: 'catalog' | 'menu' | 'button'
  children: MenuNode[]
}

export interface Profile {
  user: User
  /** 超管为 ['*'] —— 通配的处理只在 usePermission 里做一次（fe-v0.6.0） */
  perms: string[]
  menus: MenuNode[]
}
