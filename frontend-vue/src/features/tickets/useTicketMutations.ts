import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { App as AntdApp } from 'ant-design-vue'
import { computed, type Ref } from 'vue'

import {
  assignTicket,
  createTicket,
  deleteTicket,
  fetchAssignableUsers,
  fetchTicket,
  updateTicket,
  type TicketPayload,
} from '@/api/tickets'

export function useTicketQuery(id: Ref<number>) {
  return useQuery({
    queryKey: computed(() => ['ticket', id.value]),
    queryFn: () => fetchTicket(id.value),
    // ⚠️ 404 不重试。它不是网络抖动，重试三次只是让用户多等两秒
    //    才看到同一个「不存在或你无权访问」。
    retry: false,
    // ⚠️ enabled 也要 computed（V-ADR-009）——写成 `Number.isFinite(id.value)`
    //    会在 setup 时求值一次就定死。
    enabled: computed(() => Number.isFinite(id.value)),
  })
}

export function useAssignableUsers(enabled: Ref<boolean>) {
  return useQuery({
    queryKey: computed(() => ['assignable-users']),
    queryFn: fetchAssignableUsers,
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * 写操作。
 *
 * ⚠️ 成功后一律 `invalidate`，**不在本地改数据**。
 *
 *    本地删掉那一行看起来更快，但分页数字会立刻不对（还显示 50，实际 49），
 *    而且下一页的数据没补上来。
 *    **分页和计数的真相在后端**——这是 V-ADR-015 的又一个形态。
 *
 * ⚠️ `useMutation` 的 `onSuccess` 在 v5 里**仍然存在**（被移除的是
 *    `useQuery` 的）。两个适配层在这一点上完全一致。
 *
 * 🔴 `message` 走 `App.useApp()` 而不是静态 import —— 静态方法在组件树**之外**
 *    渲染，拿不到 <ConfigProvider> 的配置（vue-v0.9.0 实测：静态
 *    Modal.confirm 的按钮会渲染成「确 定」）。**与 React 版做法相同。**
 */
export function useTicketMutations(id?: Ref<number>) {
  const queryClient = useQueryClient()
  const { message } = AntdApp.useApp()

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['tickets'] })
    if (id !== undefined) {
      void queryClient.invalidateQueries({ queryKey: ['ticket', id.value] })
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
    mutationFn: (payload: TicketPayload) => updateTicket(id!.value, payload),
    onSuccess: () => {
      message.success('工单已更新')
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (targetId: number) => deleteTicket(targetId),
    onSuccess: () => {
      message.success('工单已删除')
      void queryClient.invalidateQueries({ queryKey: ['tickets'] })
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
