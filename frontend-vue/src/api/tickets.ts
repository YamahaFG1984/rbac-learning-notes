import { client } from './client'

export type TicketStatus = 'open' | 'processing' | 'closed'
export type TicketPriority = 1 | 2 | 3

export interface Ticket {
  id: number
  title: string
  content: string
  priority: TicketPriority
  status: TicketStatus
  status_display: string
  creator: number
  creator_name: string
  assignee: number | null
  department: number
  department_name: string
  created_at: string
  updated_at: string
}

/** DRF PageNumberPagination 的响应形状 */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface TicketListParams {
  page: number
  page_size?: number
  kw?: string
  status?: TicketStatus | ''
  priority?: TicketPriority | ''
}

/**
 * ⚠️ 返回的 `count` 是**经过数据权限过滤后**的数量。
 *
 *    cs_staff 拿到 5，cs_manager 拿到 50 —— 这个差异前端**什么都不用做**，
 *    它是后端 `build_scope_q()` 的结果。前端只负责渲染 results。
 *
 *    见 V-ADR-015 / F-ADR-015：前端绝不做数据的二次过滤。
 *
 * 🟢 本文件与 React 版 `frontend/src/api/tickets.ts` **逐字相同**。
 */
export async function fetchTickets(params: TicketListParams) {
  const { data } = await client.get<Paginated<Ticket>>('/tickets/', { params })
  return data
}

export async function fetchTicket(id: number) {
  const { data } = await client.get<Ticket>(`/tickets/${id}/`)
  return data
}

/**
 * 导出。
 *
 * ⚠️ 不在前端拼 CSV。前端拼的话导出的是「当前页」而不是「全部有权限的数据」，
 *    而且绕过了后端的 `ticket:ticket:export` 权限校验——
 *    一个只有 view 权限的人就能导出全表。
 *
 *    直接开新窗口让浏览器下载，同域下 Cookie 会自动带上。
 *
 * ⚠️ **已知瑕疵**（与 React 版一致）：这样就绕过了 axios 拦截器，
 *    403 时用户会看到一个下载失败的空文件而不是提示。
 *    接受它，因为 `<Can>` 已经隐藏了无权限用户的导出按钮，
 *    而真正越权的人本来就该看到失败。**记在明处，不假装它不存在。**
 */
export function exportTicketsUrl(params: Omit<TicketListParams, 'page'>) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  }
  const suffix = qs.toString()
  return `/api/v1/tickets/export/${suffix ? `?${suffix}` : ''}`
}

export interface Assignee {
  id: number
  username: string
  real_name: string
  department_name: string
}

/**
 * 派单候选人。
 *
 * ⚠️ 走 `/tickets/assignable-users/` 而不是 `/users/`。
 *    后者要 `system:user:view`，而 cs_manager 只有 assign 权限——
 *    复用它等于强迫「能派单的人」都得有「用户管理」权限，
 *    **权限点会被业务需求倒逼着变粗**，这是权限模型腐化的典型路径。
 *
 * 📌 React 阶段（fe-v0.11.0）在这里挖出过一个**真实漏洞**：
 *    派单下拉框列出了全部 6 个用户，而 cs_manager 没有 system:user:view，
 *    却能看到完整的员工名册。后端已经修好（apps/tickets/services.py::
 *    get_assignable_users，走 get_user_dept_ids，ADR-016）。
 *    **Vue 版直接受益——但仍然要验证一次，别因为「后端修过了」就假定前端调对了接口。**
 */
export async function fetchAssignableUsers() {
  const { data } = await client.get<Assignee[]>('/tickets/assignable-users/')
  return data
}

/** 新建/编辑允许提交的字段。⚠️ 没有 creator / department —— 见 TicketForm 注释 */
export interface TicketPayload {
  title: string
  content: string
  priority: TicketPriority
  status: TicketStatus
  assignee: number | null
}

export async function createTicket(payload: TicketPayload) {
  const { data } = await client.post<Ticket>('/tickets/', payload)
  return data
}

export async function updateTicket(id: number, payload: TicketPayload) {
  const { data } = await client.put<Ticket>(`/tickets/${id}/`, payload)
  return data
}

export async function deleteTicket(id: number) {
  await client.delete(`/tickets/${id}/`)
}

export async function assignTicket(id: number, assignee: number | null) {
  const { data } = await client.post<Ticket>(`/tickets/${id}/assign/`, { assignee })
  return data
}
