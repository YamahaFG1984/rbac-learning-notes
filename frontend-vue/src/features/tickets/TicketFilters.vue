<script setup lang="ts">
import { InputSearch, Select, Space } from 'ant-design-vue'

import type { TicketListParams } from '@/api/tickets'

/**
 * ⚠️ 每次改筛选条件都要把 `page` 重置回 1。
 *
 *    不重置的话：用户在第 4 页筛一个只有 3 条结果的条件，
 *    页面显示「暂无数据」——因为第 4 页确实是空的。
 *    用户会以为筛选坏了。
 *
 *    **这个坑与框架无关**，React 版注释里已经记过。
 *
 * 🟡 与 React 版的差异只有绑值方式：`v-model:value` ← 受控 prop + onChange。
 */
defineProps<{ params: TicketListParams }>()
const emit = defineEmits<{ change: [patch: Partial<TicketListParams>] }>()

function patch(p: Partial<TicketListParams>) {
  emit('change', { ...p, page: 1 })
}

const STATUS_OPTIONS = [
  { value: 'open', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'closed', label: '已关闭' },
]

const PRIORITY_OPTIONS = [
  { value: 1, label: '低' },
  { value: 2, label: '中' },
  { value: 3, label: '高' },
]
</script>

<template>
  <Space style="margin-bottom: 16px" wrap>
    <InputSearch
      placeholder="搜索标题或内容"
      allow-clear
      :default-value="params.kw"
      style="width: 240px"
      @search="(value: string) => patch({ kw: value })"
    />
    <Select
      placeholder="状态"
      allow-clear
      :value="params.status || undefined"
      style="width: 120px"
      :options="STATUS_OPTIONS"
      @change="(v) => patch({ status: (v as TicketListParams['status']) ?? '' })"
    />
    <Select
      placeholder="优先级"
      allow-clear
      :value="params.priority || undefined"
      style="width: 120px"
      :options="PRIORITY_OPTIONS"
      @change="(v) => patch({ priority: (v as TicketListParams['priority']) ?? '' })"
    />
  </Space>
</template>
