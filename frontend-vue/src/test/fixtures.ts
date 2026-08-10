import type { MenuNode, Profile } from '@/types/auth'

/**
 * 与后端 `apps/common/demo.py` 对齐的测试数据。
 *
 * 🔴 数字必须和后端一模一样。
 *
 *    后端的演示世界定义了：cs_manager 看 50 条、cs_staff 看 5 条……
 *    前端 fixtures 用另一套数字的话，前端测试全绿、一接真后端就崩——
 *    **测的不是同一个系统**。
 *
 *    对照后端 tests/test_permission_matrix.py 的 SCOPE_MATRIX，
 *    以及 e2e/ticket-list.spec.ts 里同一份矩阵。
 */

/** 与 apps/common/demo.py::build_demo_world 一致 */
export const SCOPE_MATRIX: Record<string, number> = {
  superadmin: 80,
  sysadmin: 80,
  cs_manager: 50,
  cs_staff: 5,
  no_role: 0,
}

function menu(
  id: number,
  name: string,
  routePath: string | null,
  component: string | null,
  permCode: string | null,
  children: MenuNode[] = [],
): MenuNode {
  return {
    id,
    name,
    icon: '',
    url: null,
    routePath,
    component,
    permCode,
    perm_type: routePath ? 'menu' : 'catalog',
    children,
  }
}

const TICKET_MENU = menu(1, '工单管理', null, null, null, [
  menu(2, '工单列表', '/tickets', 'tickets/List', 'ticket:ticket:view'),
])

const SYSTEM_MENUS = [
  menu(4, '组织管理', null, null, null, [
    menu(5, '部门管理', '/system/depts', 'system/Departments', 'system:dept:view'),
    menu(6, '用户管理', '/system/users', 'system/Users', 'system:user:view'),
  ]),
  menu(7, '权限管理', null, null, null, [
    menu(8, '角色管理', '/system/roles', 'system/Roles', 'system:role:view'),
    menu(9, '权限点', '/system/perms', 'system/Permissions', 'system:perm:view'),
  ]),
]

export const KNOWN_ROUTES = [
  '/tickets',
  '/system/depts',
  '/system/users',
  '/system/roles',
  '/system/perms',
  '/monitor/audit',
]

/** 客服专员：仅本人（SELF_ONLY），只有工单的看/建/改 */
export const CS_STAFF_PROFILE: Profile = {
  user: {
    id: 4,
    username: 'cs_staff',
    realName: '李专员',
    department: { id: 3, name: '客服一组' },
    isSuperuser: false,
  },
  perms: ['ticket:ticket:view', 'ticket:ticket:create', 'ticket:ticket:update'],
  menus: [TICKET_MENU],
  knownRoutes: KNOWN_ROUTES,
}

/** 客服主管：继承客服专员 + 派单/导出/删除，本部门及以下 */
export const CS_MANAGER_PROFILE: Profile = {
  user: {
    id: 3,
    username: 'cs_manager',
    realName: '王主管',
    department: { id: 2, name: '客服部' },
    isSuperuser: false,
  },
  perms: [
    // 继承自客服专员
    'ticket:ticket:view',
    'ticket:ticket:create',
    'ticket:ticket:update',
    // 自己的
    'ticket:ticket:assign',
    'ticket:ticket:export',
    'ticket:ticket:delete',
  ],
  menus: [TICKET_MENU],
  knownRoutes: KNOWN_ROUTES,
}

/**
 * 超管：`['*']` 通配。
 *
 * ⚠️ 后端的 ALL_PERMS 哨兵不可序列化，约定用 ['*'] 表示全部放行。
 *    这个约定只在 usePermission 里处理一次（fe-v0.6.0）。
 */
export const SUPERADMIN_PROFILE: Profile = {
  user: {
    id: 1,
    username: 'superadmin',
    realName: '超级管理员',
    department: { id: 1, name: '总部' },
    isSuperuser: true,
  },
  perms: ['*'],
  menus: [TICKET_MENU, ...SYSTEM_MENUS],
  knownRoutes: KNOWN_ROUTES,
}

/** 无角色：最重要的一个 fixture —— 默认拒绝的形态 */
export const NO_ROLE_PROFILE: Profile = {
  user: {
    id: 5,
    username: 'no_role',
    realName: '新人',
    department: { id: 3, name: '客服一组' },
    isSuperuser: false,
  },
  perms: [],
  menus: [],
  knownRoutes: KNOWN_ROUTES,
}

export const PROFILES: Record<string, Profile> = {
  superadmin: SUPERADMIN_PROFILE,
  cs_manager: CS_MANAGER_PROFILE,
  cs_staff: CS_STAFF_PROFILE,
  no_role: NO_ROLE_PROFILE,
}
