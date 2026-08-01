// ⚙️ 此文件由 `python manage.py export_perm_constants` 生成，请勿手工编辑。
//
// 后端权限点变更后重新生成；CI 会校验它与后端一致。
// 用法：<Can perm={PERM.TICKET_TICKET_DELETE}>
//
// perm 的类型是 PermCode 而不是 string —— 写错的权限码**编译期就报错**，
// 不会像模板版那样静默地不渲染按钮（F-ADR-012）。

export const PERM = {
  /** 审计日志 */
  SYSTEM_AUDIT_VIEW: 'system:audit:view',
  /** 新建部门 */
  SYSTEM_DEPT_CREATE: 'system:dept:create',
  /** 删除部门 */
  SYSTEM_DEPT_DELETE: 'system:dept:delete',
  /** 编辑部门 */
  SYSTEM_DEPT_UPDATE: 'system:dept:update',
  /** 部门管理 */
  SYSTEM_DEPT_VIEW: 'system:dept:view',
  /** 权限点 */
  SYSTEM_PERM_VIEW: 'system:perm:view',
  /** 分配权限 */
  SYSTEM_ROLE_ASSIGN_PERM: 'system:role:assign_perm',
  /** 新建角色 */
  SYSTEM_ROLE_CREATE: 'system:role:create',
  /** 删除角色 */
  SYSTEM_ROLE_DELETE: 'system:role:delete',
  /** 编辑角色 */
  SYSTEM_ROLE_UPDATE: 'system:role:update',
  /** 角色管理 */
  SYSTEM_ROLE_VIEW: 'system:role:view',
  /** 分配角色 */
  SYSTEM_USER_ASSIGN_ROLE: 'system:user:assign_role',
  /** 新建用户 */
  SYSTEM_USER_CREATE: 'system:user:create',
  /** 删除用户 */
  SYSTEM_USER_DELETE: 'system:user:delete',
  /** 编辑用户 */
  SYSTEM_USER_UPDATE: 'system:user:update',
  /** 用户管理 */
  SYSTEM_USER_VIEW: 'system:user:view',
  /** 派单 */
  TICKET_TICKET_ASSIGN: 'ticket:ticket:assign',
  /** 新建工单 */
  TICKET_TICKET_CREATE: 'ticket:ticket:create',
  /** 删除工单 */
  TICKET_TICKET_DELETE: 'ticket:ticket:delete',
  /** 导出工单 */
  TICKET_TICKET_EXPORT: 'ticket:ticket:export',
  /** 编辑工单 */
  TICKET_TICKET_UPDATE: 'ticket:ticket:update',
  /** 工单列表 */
  TICKET_TICKET_VIEW: 'ticket:ticket:view',
} as const

export type PermCode = (typeof PERM)[keyof typeof PERM]
