<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import {
  Descriptions,
  DescriptionsItem,
  InputSearch,
  Modal,
  Space,
  Table,
  Tag,
} from 'ant-design-vue'
import { computed, ref } from 'vue'

import { fetchAuditLogs, type AuditLog } from '@/api/admin'
import { useTableQuery } from '@/hooks/useTableQuery'
import PageContainer from '@/layouts/PageContainer.vue'

type LogQuery = { page: number; kw: string; action: string }
const DEFAULTS: LogQuery = { page: 1, kw: '', action: '' }

const { params, setParams } = useTableQuery(DEFAULTS)
const detail = ref<AuditLog | null>(null)

const query = useQuery({
  queryKey: computed(() => ['audit-logs', params.value]),
  queryFn: () => fetchAuditLogs(params.value),
})

/**
 * 把 `detail` 里的 added / removed 渲染成一眼能读的东西。
 *
 * ⚠️ 直接 `JSON.stringify` 出来没人看得懂。
 *
 *    后端 v0.17.0 记录 before/after/added/removed 的理由是
 *    「审计日志要能回答『当时到底发生了什么』」——
 *    展示层不做处理的话，这个价值就打折了。
 *    **一条没人读得懂的日志，和没有这条日志的区别不大。**
 *
 * 🟡 React 版把它写成一个 `<DetailDiff>` 子组件；
 *    Vue 这里用两个 computed + 模板片段，省掉一个文件。
 *    行为相同。
 */
function diffOf(d: Record<string, unknown>) {
  return {
    added: (d.added as string[]) ?? [],
    removed: (d.removed as string[]) ?? [],
  }
}

const pagination = computed(() => ({
  current: params.value.page,
  total: query.data.value?.count ?? 0,
  pageSize: 20,
  showTotal: (t: number) => `共 ${t} 条`,
  showSizeChanger: false,
}))

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作者', dataIndex: 'actor_name', key: 'actor_name', width: 120 },
  { title: '动作', dataIndex: 'action_display', width: 130 },
  { title: '目标', dataIndex: 'target_repr', key: 'target_repr', width: 160 },
  { title: '变更', key: 'diff' },
  { title: '结果', dataIndex: 'result', key: 'result', width: 80 },
  { title: 'IP', dataIndex: 'ip', width: 130 },
]

const ts = (v: string) => v.replace('T', ' ').slice(0, 19)
</script>

<template>
  <PageContainer title="审计日志">
    <InputSearch
      placeholder="搜索操作者或目标"
      allow-clear
      :default-value="params.kw"
      style="width: 260px; margin-bottom: 16px"
      @search="(kw: string) => setParams({ kw, page: 1 })"
    />

    <Table
      row-key="id"
      :loading="query.isFetching.value"
      :data-source="query.data.value?.results ?? []"
      :columns="columns"
      :pagination="pagination"
      :custom-row="(row: AuditLog) => ({ onClick: () => (detail = row) })"
      @change="(p: { current?: number }) => setParams({ page: p.current ?? 1 })"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'created_at'">
          {{ ts((record as AuditLog).created_at) }}
        </template>
        <!-- 冗余快照：用户被删除后 actor 变 null，但这里还留着当时是谁 -->
        <template v-else-if="column.key === 'actor_name'">
          {{ (record as AuditLog).actor_name || '（已删除）' }}
        </template>
        <template v-else-if="column.key === 'target_repr'">
          {{ (record as AuditLog).target_repr || '—' }}
        </template>
        <template v-else-if="column.key === 'diff'">
          <Space :size="[0, 4]" wrap>
            <Tag
              v-for="code in diffOf((record as AuditLog).detail).added"
              :key="`+${code}`"
              color="green"
            >
              + {{ code }}
            </Tag>
            <Tag
              v-for="code in diffOf((record as AuditLog).detail).removed"
              :key="`-${code}`"
              color="red"
            >
              − {{ code }}
            </Tag>
          </Space>
        </template>
        <template v-else-if="column.key === 'result'">
          <Tag :color="(record as AuditLog).result === 'success' ? 'green' : 'red'">
            {{ (record as AuditLog).result_display }}
          </Tag>
        </template>
      </template>
    </Table>

    <Modal
      :open="detail !== null"
      title="审计详情"
      :footer="null"
      :width="720"
      @cancel="detail = null"
    >
      <template v-if="detail">
        <Descriptions bordered :column="2" size="small">
          <DescriptionsItem label="时间">{{ ts(detail.created_at) }}</DescriptionsItem>
          <DescriptionsItem label="操作者">
            {{ detail.actor_name || '（已删除）' }}
          </DescriptionsItem>
          <DescriptionsItem label="动作">{{ detail.action_display }}</DescriptionsItem>
          <DescriptionsItem label="目标">{{ detail.target_repr || '—' }}</DescriptionsItem>
          <DescriptionsItem label="IP">{{ detail.ip ?? '—' }}</DescriptionsItem>
          <DescriptionsItem label="结果">{{ detail.result_display }}</DescriptionsItem>
        </Descriptions>

        <div style="margin-top: 16px">
          <Space :size="[0, 4]" wrap>
            <Tag v-for="code in diffOf(detail.detail).added" :key="`+${code}`" color="green">
              + {{ code }}
            </Tag>
            <Tag v-for="code in diffOf(detail.detail).removed" :key="`-${code}`" color="red">
              − {{ code }}
            </Tag>
          </Space>
        </div>

        <!-- 结构化展示之外仍保留原始 JSON —— 展示层的解读可能有遗漏，
             原始记录才是审计的依据 -->
        <pre
          style="
            margin-top: 12px;
            padding: 12px;
            background: rgba(0, 0, 0, 0.04);
            border-radius: 4px;
            font-size: 12px;
            max-height: 280px;
            overflow: auto;
          "
          >{{ JSON.stringify(detail.detail, null, 2) }}</pre
        >
      </template>
    </Modal>
  </PageContainer>
</template>
