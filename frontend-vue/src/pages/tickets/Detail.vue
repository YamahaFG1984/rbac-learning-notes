<script setup lang="ts">
import { Button, Descriptions, DescriptionsItem, Skeleton, Tag } from 'ant-design-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { TicketPayload } from '@/api/tickets'
import Can from '@/components/Can.vue'
import ErrorResult from '@/components/ErrorResult.vue'
import ResourceNotFound from '@/components/ResourceNotFound.vue'
import { PERM } from '@/constants/permissions'
import AssignModal from '@/features/tickets/AssignModal.vue'
import TicketForm from '@/features/tickets/TicketForm.vue'
import {
  useTicketMutations,
  useTicketQuery,
} from '@/features/tickets/useTicketMutations'
import PageContainer from '@/layouts/PageContainer.vue'

const PRIORITY: Record<number, string> = { 1: '低', 2: '中', 3: '高' }

const route = useRoute()
const router = useRouter()

const ticketId = computed(() => Number(route.params.id))

const { data, error, isLoading } = useTicketQuery(ticketId)
const { update, remove, assign } = useTicketMutations(ticketId)

const editing = ref(false)
const assigning = ref(false)
const formRef = ref<InstanceType<typeof TicketForm> | null>(null)

/*
 * 🔴 404 必须**整页替换**，不能只弹个 toast。
 *
 *    弹 toast 的话用户停在一个空白页上，不知道该干什么；
 *    而且 toast 三秒后消失，刷新一次就再也看不到原因了。
 *
 *    全局拦截器负责通用处理（vue-v0.12.0），
 *    「详情页拿不到数据」这种是页面级的事，页面自己管。
 */
const httpStatus = computed(
  () => (error.value as { response?: { status?: number } } | null)?.response?.status,
)

async function onUpdate(payload: TicketPayload) {
  try {
    await update.mutateAsync(payload)
    editing.value = false
  } catch (err) {
    formRef.value?.showServerError(err)
  }
}

async function onAssign(assignee: number | null) {
  try {
    await assign.mutateAsync({ targetId: ticketId.value, assignee })
    assigning.value = false
  } catch {
    // 拦截器已经提示过了
  }
}

async function onRemove() {
  await remove.mutateAsync(ticketId.value)
  void router.push('/tickets')
}
</script>

<template>
  <Skeleton v-if="isLoading" active />
  <ResourceNotFound v-else-if="httpStatus === 404" />
  <ErrorResult v-else-if="error || !data" />

  <PageContainer v-else :title="data.title">
    <template #extra>
      <Can :perm="PERM.TICKET_TICKET_UPDATE">
        <Button @click="editing = true">编辑</Button>
      </Can>
      <Can :perm="PERM.TICKET_TICKET_ASSIGN">
        <Button @click="assigning = true">派单</Button>
      </Can>
      <Can :perm="PERM.TICKET_TICKET_DELETE">
        <Button danger :loading="remove.isPending.value" @click="onRemove">
          删除
        </Button>
      </Can>
    </template>

    <Descriptions bordered :column="2" size="middle">
      <DescriptionsItem label="状态">{{ data.status_display }}</DescriptionsItem>
      <DescriptionsItem label="优先级">
        <Tag>{{ PRIORITY[data.priority] ?? data.priority }}</Tag>
      </DescriptionsItem>
      <!--
        creator / department 只读展示 —— 它们由后端从 request.user 快照，
        界面上没有任何地方能改它们（同模板版的白名单 fields）。
      -->
      <DescriptionsItem label="创建人">{{ data.creator_name }}</DescriptionsItem>
      <DescriptionsItem label="归属部门">{{ data.department_name }}</DescriptionsItem>
      <DescriptionsItem label="创建时间">
        {{ data.created_at.replace('T', ' ').slice(0, 16) }}
      </DescriptionsItem>
      <DescriptionsItem label="更新时间">
        {{ data.updated_at.replace('T', ' ').slice(0, 16) }}
      </DescriptionsItem>
      <DescriptionsItem label="内容" :span="2">
        <div style="white-space: pre-wrap">{{ data.content || '（无）' }}</div>
      </DescriptionsItem>
    </Descriptions>

    <TicketForm
      ref="formRef"
      :open="editing"
      :ticket="data"
      :confirm-loading="update.isPending.value"
      @cancel="editing = false"
      @submit="onUpdate"
    />
    <AssignModal
      :open="assigning"
      :current-assignee="data.assignee"
      :confirm-loading="assign.isPending.value"
      @cancel="assigning = false"
      @submit="onAssign"
    />
  </PageContainer>
</template>
