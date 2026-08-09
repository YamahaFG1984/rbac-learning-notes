<script setup lang="ts">
import { App as AntdApp, Button, Space, Table, Tag } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  exportTicketsUrl,
  type Ticket,
  type TicketPayload,
  type TicketPriority,
  type TicketStatus,
} from '@/api/tickets'
import { usePermission } from '@/auth/usePermission'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import AssignModal from '@/features/tickets/AssignModal.vue'
import TicketFilters from '@/features/tickets/TicketFilters.vue'
import TicketForm from '@/features/tickets/TicketForm.vue'
import { useTicketList } from '@/features/tickets/useTicketList'
import { useTicketMutations } from '@/features/tickets/useTicketMutations'
import { useTableQuery } from '@/hooks/useTableQuery'
import PageContainer from '@/layouts/PageContainer.vue'

/**
 * 🟡 React 版这里有一条注释说「必须是 `type` 不能是 `interface`」——
 *    TS 只给类型别名隐式索引签名，`useTableQuery` 的
 *    `T extends Record<string, string | number>` 约束会拒绝 interface。
 *    报错指向字段，实际和字段毫无关系。
 *
 *    **这条限制与框架无关**（是 TS 的规则），Vue 版原样适用。
 */
type TicketQuery = {
  page: number
  kw: string
  status: TicketStatus | ''
  priority: TicketPriority | ''
}

/**
 * ⚠️ 这些值来自 URL，用户可以随便改成 `?status=xyz`。
 *    类型标注在这里是**一厢情愿**的——TS 管不到运行时的 URL。
 *
 *    这没关系：后端拿到无效值只会筛出 0 条，**不可能筛出更多**。
 *    （`tests/api/test_api_permissions.py::test_filter_cannot_widen_scope`
 *      就是在钉这一点：任何筛选参数都只能收窄，不能放宽。）
 *    前端不必为此做校验——校验放在这里又是一层会漂移的重复逻辑。
 */
const DEFAULTS: TicketQuery = { page: 1, kw: '', status: '', priority: '' }

const PRIORITY_TAG: Record<number, { color: string; text: string }> = {
  1: { color: 'default', text: '低' },
  2: { color: 'blue', text: '中' },
  3: { color: 'red', text: '高' },
}

const { params, setParams } = useTableQuery(DEFAULTS)
const query = useTicketList(params)

const { can } = usePermission()

/*
 * ⚠️ 必须是 computed（V-ADR-009 那一类）。
 *    🟡 React 版这里是 `useMemo(..., [can])`——它的默认行为是每次重算，
 *       useMemo 只是**阻止**重算；Vue 的默认是不重算，computed 是**启用**重算。
 */
const columns = computed<ColumnsType<Ticket>>(() => [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '状态', dataIndex: 'status_display', width: 100 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
  { title: '创建人', dataIndex: 'creator_name', width: 110 },
  { title: '归属部门', dataIndex: 'department_name', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  /*
   * ⚠️ 一个操作都没有的用户，不该看到一列空白的「操作」。
   *
   *    列的增减是**数据**层面的判断，只能用 composable 式；
   *    列内每个按钮才用组件式 <Can>。两种接口各司其职。
   */
  ...(can(PERM.TICKET_TICKET_UPDATE) ||
  can(PERM.TICKET_TICKET_DELETE) ||
  can(PERM.TICKET_TICKET_ASSIGN)
    ? [{ title: '操作', key: 'action', width: 160 }]
    : []),
])

const pagination = computed(() => ({
  current: params.value.page,
  /*
   * ⚠️ total 直接用后端的 count，**不重新计算**。
   *
   *    前端如果对 results 再过滤一次，这里就会出现
   *    「显示 40 条，分页器说 50 条」的经典错位——
   *    而且那次过滤零安全价值：数据早就到浏览器了（V-ADR-015）。
   */
  total: query.data.value?.count ?? 0,
  pageSize: 20,
  showTotal: (total: number) => `共 ${total} 条`,
  showSizeChanger: false,
}))

function onTableChange(p: { current?: number }) {
  setParams({ page: p.current ?? 1 })
}

function onExport() {
  window.open(exportTicketsUrl(params.value))
}

// ─────────────────────────────────────────────────────────────
// 写操作（vue-v0.9.0）
// ─────────────────────────────────────────────────────────────

const { create, remove, assign } = useTicketMutations()

const creating = ref(false)
const assigningId = ref<number | null>(null)
const formRef = ref<InstanceType<typeof TicketForm> | null>(null)

const assigningTicket = computed(() =>
  query.data.value?.results.find((t) => t.id === assigningId.value),
)

async function onCreate(payload: TicketPayload) {
  try {
    await create.mutateAsync(payload)
    creating.value = false
  } catch (err) {
    formRef.value?.showServerError(err)
  }
}

async function onAssign(assignee: number | null) {
  try {
    await assign.mutateAsync({ targetId: assigningId.value!, assignee })
    assigningId.value = null
  } catch {
    // 拦截器已经提示过了
  }
}

/*
 * ⚠️ 删除必须二次确认。
 *
 *    这不只是体验问题：列表页的删除按钮和行是对齐的，
 *    误点一行删掉另一行的数据是真实会发生的事。
 *    确认框里带上标题，让用户确认的是「这一条」而不是「删除」这个动作。
 *
 * 🔴📌 **必须用 `App.useApp()` 拿到的 `modal`，不能 import 静态的 `Modal`。**
 *
 *    静态方法在组件树**之外**渲染，拿不到 `<ConfigProvider>` 的配置。
 *    实测：静态 `Modal.confirm()` 的按钮渲染成 **「取 消」「确 定」**，
 *    而同一页面里树内的按钮是正确的「删除」「派单」——
 *    `auto-insert-space-in-button="false"` 对它完全无效。
 *
 *    后果是所有按文本找确认框按钮的代码（含 E2E）全部失效，
 *    而报错只说「找不到元素」。
 *
 *    🟢 React 版早就这么做了（`App.useApp()`）——**这是我没照抄到位，
 *       不是框架差异。**
 */
const { modal } = AntdApp.useApp()

function confirmRemove(row: Ticket) {
  modal.confirm({
    title: '确认删除？',
    content: `工单「${row.title}」将被删除，此操作不可撤销。`,
    okType: 'danger',
    okText: '确定',
    cancelText: '取消',
    onOk: () => remove.mutateAsync(row.id),
  })
}
</script>

<template>
  <PageContainer title="工单列表">
    <template #extra>
      <Can :perm="PERM.TICKET_TICKET_CREATE">
        <Button type="primary" @click="creating = true">新建工单</Button>
      </Can>
      <Can :perm="PERM.TICKET_TICKET_EXPORT">
        <!--
          导出走后端同一条 .for_user() 链路。
          前端自己拼 CSV 的话导出的是「当前页」，而且绕过了 EXPORT 权限。
        -->
        <Button @click="onExport">导出</Button>
      </Can>
    </template>

    <TicketFilters :params="params" @change="setParams" />

    <Table
      row-key="id"
      :columns="columns"
      :data-source="query.data.value?.results ?? []"
      :loading="query.isFetching.value"
      :pagination="pagination"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'title'">
          <RouterLink :to="`/tickets/${(record as Ticket).id}`">
            {{ (record as Ticket).title }}
          </RouterLink>
        </template>

        <template v-else-if="column.key === 'priority'">
          <Tag :color="PRIORITY_TAG[(record as Ticket).priority]?.color">
            {{
              PRIORITY_TAG[(record as Ticket).priority]?.text ??
              (record as Ticket).priority
            }}
          </Tag>
        </template>

        <template v-else-if="column.key === 'created_at'">
          {{ (record as Ticket).created_at.replace('T', ' ').slice(0, 16) }}
        </template>

        <template v-else-if="column.key === 'action'">
          <Space :size="4">
            <Can :perm="PERM.TICKET_TICKET_UPDATE">
              <RouterLink :to="`/tickets/${(record as Ticket).id}`">编辑</RouterLink>
            </Can>
            <!--
              📌 「派单」在**行**里，不在工具栏——它是针对某一条工单的操作
                 （后端路由是 /tickets/<pk>/assign/）。
                 React 版 fe-v0.9.0 放错了位置，fe-v0.10.0 才改。
                 功能在 vue-v0.9.0 接上，本 tag 只占位。
            -->
            <Can :perm="PERM.TICKET_TICKET_ASSIGN">
              <Button
                type="link"
                size="small"
                @click="assigningId = (record as Ticket).id"
              >
                派单
              </Button>
            </Can>
            <Can :perm="PERM.TICKET_TICKET_DELETE">
              <Button
                type="link"
                size="small"
                danger
                @click="confirmRemove(record as Ticket)"
              >
                删除
              </Button>
            </Can>
          </Space>
        </template>
      </template>
    </Table>

    <TicketForm
      ref="formRef"
      :open="creating"
      :confirm-loading="create.isPending.value"
      @cancel="creating = false"
      @submit="onCreate"
    />
    <AssignModal
      :open="assigningId !== null"
      :current-assignee="assigningTicket?.assignee ?? null"
      :confirm-loading="assign.isPending.value"
      @cancel="assigningId = null"
      @submit="onAssign"
    />
  </PageContainer>
</template>
