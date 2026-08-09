<script setup lang="ts">
import { Button, Space, Table } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { computed } from 'vue'

import { usePermission } from '@/auth/usePermission'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import PageContainer from '@/layouts/PageContainer.vue'

interface Row {
  id: number
  title: string
  status: string
}

/** 真实数据在 vue-v0.8.0 接。本 tag 只关心「按钮该不该出现」。 */
const ROWS: Row[] = [{ id: 1, title: '（vue-v0.8.0 接真实数据）', status: '待处理' }]

/*
 * composable 式：用于**数据**。
 *
 * antdv 的 columns / items / disabled 都是数据不是模板，包不进 <Can>。
 * 所以两个接口都要——但它们内部是同一个判断函数（usePermission → store.can）。
 */
const { can } = usePermission()

/*
 * ⚠️ 必须是 computed。写成普通数组的话，vue-v0.11.0 权限变更后
 *    「操作」列不会消失/恢复。
 *
 *    🟡 React 版这里是普通数组——组件函数每次渲染都重新执行，天然重算。
 *       **同一个需求，Vue 需要显式声明响应式，React 不需要。**
 *       忘了写的后果方向相反：React 是多算几次（性能），Vue 是不更新（正确性）。
 */
const columns = computed<ColumnsType<Row>>(() => [
  { title: '标题', dataIndex: 'title' },
  { title: '状态', dataIndex: 'status' },
  // 一个操作都没有的用户，不该看到一列空白的「操作」
  ...(can(PERM.TICKET_TICKET_UPDATE) ||
  can(PERM.TICKET_TICKET_DELETE) ||
  can(PERM.TICKET_TICKET_ASSIGN)
    ? [{ title: '操作', key: 'action' }]
    : []),
])
</script>

<template>
  <PageContainer title="工单列表">
    <template #extra>
      <!--
        组件式：用于**渲染**。

        ⚠️ 每一个 <Can> 都必须有一个对应的后端 perm_map 项，成对出现。
           vue-v0.13.0 的结构性测试会自动对账。

        📌 「派单」**不在这里**——它是针对某一条工单的操作，
           按钮属于行操作列（见下面的 #bodyCell）。

           React 版 fe-v0.9.0 把它放进了工具栏，fe-v0.10.0 才移到行里，
           导致 fe-v0.9.0 的 E2E 变红。**Vue 版直接写对**——
           这是「已经走过一遍」的红利之一。
      -->
      <Can :perm="PERM.TICKET_TICKET_CREATE">
        <Button type="primary">新建工单</Button>
      </Can>
      <Can :perm="PERM.TICKET_TICKET_EXPORT">
        <Button>导出</Button>
      </Can>
    </template>

    <Table :columns="columns" :data-source="ROWS" row-key="id" :pagination="false">
      <template #bodyCell="{ column }">
        <template v-if="column.key === 'action'">
          <Space>
            <Can :perm="PERM.TICKET_TICKET_UPDATE">
              <Button type="link" size="small">编辑</Button>
            </Can>
            <Can :perm="PERM.TICKET_TICKET_ASSIGN">
              <Button type="link" size="small">派单</Button>
            </Can>
            <Can :perm="PERM.TICKET_TICKET_DELETE">
              <Button type="link" size="small" danger>删除</Button>
            </Can>
          </Space>
        </template>
      </template>
    </Table>
  </PageContainer>
</template>
