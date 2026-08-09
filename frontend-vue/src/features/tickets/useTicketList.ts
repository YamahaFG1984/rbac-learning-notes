import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'

import { fetchTickets, type TicketListParams } from '@/api/tickets'

/**
 * 工单列表。
 *
 * 🔴🔴 **本文件是 V-ADR-009 的现场，也是本阶段最会静默失效的一处。**
 *
 * ⚠️ 参数类型是 `Ref<TicketListParams>` 而不是 `TicketListParams`。
 *
 *    传值的话，`useTicketList(params.value)` 在 `<script setup>` 里
 *    **只求值一次**，之后筛选条件怎么变这个函数都收不到——
 *    连 queryKey 都没机会写错，从入口就断了。
 *
 * ⚠️ `queryKey` 必须是 `computed`，不能是数组字面量：
 *
 *      ❌ queryKey: ['tickets', params.value]
 *         数组字面量在 setup 里**只求值一次** → key 定死 →
 *         换页码、改筛选，表格**纹丝不动**。
 *         **没有报错，没有警告，控制台干干净净。第一次加载还是对的。**
 *
 *      ✅ queryKey: computed(() => ['tickets', params.value])
 *
 *    📌 **React 侧这个 bug 不可能存在**——组件函数每次重新执行，
 *       `queryKey` 每次重新求值，「响应式」由重渲染天然提供。
 *
 *       React 版这里踩的是另一个坑（注释原文）：
 *       > queryKey 必须包含**全部**查询参数。只写 ['tickets'] 的话翻页时
 *       > key 不变……表现极其迷惑：**第一次换页有效**，之后就不动了。
 *
 *       **同一个库、同一个版本号（5.101.4）、两个适配层，各留一个静默失效点。**
 *       它们都长在「适配层必须适配、又无法统一」的接缝上——响应式的接入方式。
 *
 * ⚠️ `placeholderData: keepPreviousData` —— 翻页时保留上一页的数据，
 *    否则表格会先变空再填充，视觉上一跳一跳的。（与 React 版逐字相同）
 */
export function useTicketList(params: Ref<TicketListParams>) {
  return useQuery({
    queryKey: computed(() => ['tickets', params.value]),
    queryFn: () => fetchTickets(params.value),
    placeholderData: keepPreviousData,
  })
}
