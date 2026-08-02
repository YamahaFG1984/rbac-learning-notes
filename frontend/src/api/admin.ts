import { client } from './client'

// --------------------------------------------------------------------------- //
// 部门
// --------------------------------------------------------------------------- //

export interface Department {
  id: number
  code: string
  name: string
  parent: number | null
  path: string
  depth: number
  order_num: number
  is_active: boolean
}

/**
 * ⚠️ 不传 page_size —— 后端这个接口**不分页**（树不能分页）。
 *
 *    我一开始写的是 `?page_size=500`，而 DRF 没配 page_size_query_param，
 *    这个参数被**静默忽略**：拿到 20 条，页面少了几个节点，不报错。
 *    「传了一个不被识别的参数」是最难发现的一类错误——它长得像生效了。
 */
export async function fetchDepartments() {
  const { data } = await client.get<Department[]>('/departments/')
  return data
}

export type DepartmentPayload = Pick<
  Department,
  'code' | 'name' | 'parent' | 'order_num' | 'is_active'
>

export const createDepartment = (p: DepartmentPayload) =>
  client.post<Department>('/departments/', p).then((r) => r.data)
export const updateDepartment = (id: number, p: DepartmentPayload) =>
  client.put<Department>(`/departments/${id}/`, p).then((r) => r.data)
export const deleteDepartment = (id: number) => client.delete(`/departments/${id}/`)

// --------------------------------------------------------------------------- //
// 用户
// --------------------------------------------------------------------------- //

export interface AdminUser {
  id: number
  username: string
  real_name: string
  phone: string
  email: string
  department: number | null
  department_name: string
  is_active: boolean
  date_joined: string
}

/**
 * ⚠️ 提交字段是**白名单**，而且 is_superuser 永不在其中。
 *
 *    后端的 UserSerializer 也没有这个字段，但前端不该依赖那一点——
 *    「不要把安全性寄托在对端的实现细节上」。
 *
 *    安全红线 4：超管只能通过 createsuperuser 创建。
 *    否则任何有 system:user:update 的人都能自我提权。
 */
export type UserPayload = Pick<
  AdminUser,
  'username' | 'real_name' | 'phone' | 'email' | 'department' | 'is_active'
>

export interface Paginated<T> {
  count: number
  results: T[]
}

export async function fetchUsers(params: Record<string, unknown>) {
  const { data } = await client.get<Paginated<AdminUser>>('/users/', { params })
  return data
}

export const createUser = (p: UserPayload) =>
  client.post<AdminUser>('/users/', p).then((r) => r.data)
export const updateUser = (id: number, p: UserPayload) =>
  client.put<AdminUser>(`/users/${id}/`, p).then((r) => r.data)
export const deleteUser = (id: number) => client.delete(`/users/${id}/`)

export interface UserRolesPayload {
  checked: number[]
  roles: Array<{
    id: number
    name: string
    code: string
    /** 由后端的 can_grant_role 判断（ADR-011）。⚠️ 前端不重算 */
    grantable: boolean
  }>
}

export const fetchUserRoles = (id: number) =>
  client.get<UserRolesPayload>(`/users/${id}/roles/`).then((r) => r.data)
export const saveUserRoles = (id: number, roles: number[]) =>
  client.put<{ saved: number; rejected: number }>(`/users/${id}/roles/`, { roles })
    .then((r) => r.data)

// --------------------------------------------------------------------------- //
// 角色
// --------------------------------------------------------------------------- //

export interface Role {
  id: number
  code: string
  name: string
  description: string
  inherits_from: number | null
  inherits_from_name: string
  data_scope: number
  data_scope_display: string
  order_num: number
  is_builtin: boolean
  is_active: boolean
}

export type RolePayload = Pick<
  Role,
  'code' | 'name' | 'description' | 'inherits_from' | 'order_num' | 'is_active'
>

/** 角色仍然分页（它是列表不是树），数量少，第一页够用 */
export async function fetchRoles() {
  const { data } = await client.get<Paginated<Role> | Role[]>('/roles/')
  return Array.isArray(data) ? data : data.results
}

export const createRole = (p: RolePayload) =>
  client.post<Role>('/roles/', p).then((r) => r.data)
export const updateRole = (id: number, p: RolePayload) =>
  client.put<Role>(`/roles/${id}/`, p).then((r) => r.data)
export const deleteRole = (id: number) => client.delete(`/roles/${id}/`)

export interface PermNode {
  id: number
  parent: number | null
  name: string
  code: string | null
  permType: 'catalog' | 'menu' | 'button'
  depth: number
  /** 直接授予 **或** 继承而来 —— 界面上显示成勾选 */
  checked: boolean
  /**
   * 🔴 **纯继承、且不是直接授予**。只有它为 true 才禁用。
   *
   * 这个字段**必须由后端给**，前端绝不能自己算（F-ADR-006）。
   * 写成「在父角色权限里 = inherited」的话，
   * 「既直接授予又继承」的项会被禁用，而 disabled 的节点
   * 不进 AntD 的 checkedKeys —— 保存时那条直接授权被静默删掉。
   */
  inherited: boolean
}

export interface RolePermPayload {
  hasInherited: boolean
  inheritsFromName: string | null
  nodes: PermNode[]
}

export const fetchRolePermissions = (id: number) =>
  client.get<RolePermPayload>(`/roles/${id}/permissions/`).then((r) => r.data)
export const saveRolePermissions = (id: number, permissions: number[]) =>
  client
    .put<{ saved: number; rejected: number }>(`/roles/${id}/permissions/`, {
      permissions,
    })
    .then((r) => r.data)

export interface EffectivePermsPayload {
  chain: Array<{ id: number; name: string }>
  rows: Array<{ code: string; name: string; source: string; isDirect: boolean }>
}

export const fetchEffectivePermissions = (id: number) =>
  client
    .get<EffectivePermsPayload>(`/roles/${id}/effective-permissions/`)
    .then((r) => r.data)

export interface DataScopePayload {
  dataScope: number
  customValue: number
  scopes: Array<{ value: number; label: string }>
  departments: Array<{
    id: number
    parent: number | null
    name: string
    depth: number
    checked: boolean
  }>
}

export const fetchDataScope = (id: number) =>
  client.get<DataScopePayload>(`/roles/${id}/data-scope/`).then((r) => r.data)
export const saveDataScope = (
  id: number,
  dataScope: number,
  departments: number[],
) => client.put(`/roles/${id}/data-scope/`, { dataScope, departments })

// --------------------------------------------------------------------------- //
// 权限点（只读）
// --------------------------------------------------------------------------- //

export interface Permission {
  id: number
  code: string | null
  name: string
  perm_type: 'catalog' | 'menu' | 'button'
  parent: number | null
  icon: string
  is_active: boolean
  is_deprecated: boolean
}

/** 同 fetchDepartments：权限点也是树，后端不分页 */
export async function fetchPermissions() {
  const { data } = await client.get<Permission[]>('/permissions/')
  return data
}

// --------------------------------------------------------------------------- //
// 审计日志
// --------------------------------------------------------------------------- //

export interface AuditLog {
  id: number
  actor_name: string
  action: string
  action_display: string
  target_type: string
  target_repr: string
  detail: Record<string, unknown>
  ip: string | null
  result: string
  result_display: string
  created_at: string
}

export async function fetchAuditLogs(params: Record<string, unknown>) {
  const { data } = await client.get<Paginated<AuditLog>>('/audit-logs/', { params })
  return data
}
