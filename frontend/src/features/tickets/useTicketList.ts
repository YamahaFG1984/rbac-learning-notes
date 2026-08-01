import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { fetchTickets, type TicketListParams } from '@/api/tickets'

/**
 * 工单列表。
 *
 * ⚠️ queryKey 必须包含**全部**查询参数。
 *
 *    只写 ['tickets'] 的话，翻页时 key 不变，Query 认为是同一份数据，
 *    页面不刷新。表现极其迷惑：**第一次换页有效**（缓存是空的），
 *    之后就不动了——很容易被误判成后端分页坏了。
 *
 * ⚠️ placeholderData: keepPreviousData —— 翻页时保留上一页的数据，
 *    否则表格会先变空再填充，视觉上一跳一跳的。
 */
export function useTicketList(params: TicketListParams) {
  return useQuery({
    queryKey: ['tickets', params],
    queryFn: () => fetchTickets(params),
    placeholderData: keepPreviousData,
  })
}
