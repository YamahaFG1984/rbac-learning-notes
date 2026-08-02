import { App } from 'antd'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'

import {
  assignTicket,
  createTicket,
  deleteTicket,
  fetchAssignableUsers,
  fetchTicket,
  updateTicket,
  type TicketPayload,
} from '@/api/tickets'

export function useTicketQuery(id: number) {
  return useQuery({
    queryKey: ['ticket', id],
    queryFn: () => fetchTicket(id),
    // ⚠️ 404 不重试。它不是网络抖动，重试三次只是让用户多等两秒
    //    才看到同一个「不存在或你无权访问」。
    retry: false,
    enabled: Number.isFinite(id),
  })
}

export function useAssignableUsers(enabled = true) {
  return useQuery({
    queryKey: ['assignable-users'],
    queryFn: fetchAssignableUsers,
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * 写操作。
 *
 * ⚠️ 成功后一律 invalidate，**不在本地改数据**。
 *
 *    本地删掉那一行看起来更快，但分页数字会立刻不对（还显示 50，实际 49），
 *    而且下一页的数据没补上来。
 *    **分页和计数的真相在后端**——这是 F-ADR-015 的又一个形态。
 */
export function useTicketMutations(id?: number) {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['tickets'] })
    if (id !== undefined) {
      queryClient.invalidateQueries({ queryKey: ['ticket', id] })
    }
  }

  const create = useMutation({
    mutationFn: (payload: TicketPayload) => createTicket(payload),
    onSuccess: () => {
      message.success('工单已创建')
      invalidate()
    },
  })

  const update = useMutation({
    mutationFn: (payload: TicketPayload) => updateTicket(id!, payload),
    onSuccess: () => {
      message.success('工单已更新')
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (targetId: number) => deleteTicket(targetId),
    onSuccess: () => {
      message.success('工单已删除')
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })

  const assign = useMutation({
    mutationFn: (vars: { targetId: number; assignee: number | null }) =>
      assignTicket(vars.targetId, vars.assignee),
    onSuccess: () => {
      message.success('已派单')
      invalidate()
    },
  })

  return { create, update, remove, assign }
}
