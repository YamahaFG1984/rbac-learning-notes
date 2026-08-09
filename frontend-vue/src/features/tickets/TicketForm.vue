<script setup lang="ts">
import {
  App as AntdApp,
  Form,
  FormItem,
  Input,
  Modal,
  Select,
  Textarea,
} from 'ant-design-vue'
import { computed, reactive, ref, toRef, watch } from 'vue'

import type { Ticket, TicketPayload } from '@/api/tickets'
import {
  parseServerDetail,
  parseServerFieldErrors,
  type FieldErrors,
} from '@/utils/formErrors'

import { useAssignableUsers } from './useTicketMutations'

/**
 * 新建 / 编辑工单。
 *
 * ⚠️ 表单里**没有** `creator` 和 `department` 字段。
 *
 *    后端的 `TicketSerializer` 把它们设成了 read_only，提交了也会被忽略——
 *    但前端不该依赖这一点。理由是**不要把安全性寄托在对端的实现细节上**：
 *    后端某天改了 serializer，前端的伪造就会立刻生效。
 *
 *    这和模板版 `TicketForm` 用白名单 `fields` 而不是 `exclude` 是同一条原则
 *    （后端安全红线第 3 条）。
 */
const props = defineProps<{
  open: boolean
  /** 有值 = 编辑，无值 = 新建 */
  ticket?: Ticket
  confirmLoading?: boolean
}>()
const emit = defineEmits<{
  cancel: []
  submit: [payload: TicketPayload]
}>()

// 关着的时候不请求候选人 —— 打开表单才是需要它的时刻
const { message } = AntdApp.useApp()
const assignees = useAssignableUsers(toRef(props, 'open'))

const EMPTY: TicketPayload = {
  title: '',
  content: '',
  priority: 2,
  status: 'open',
  assignee: null,
}

const formState = reactive<TicketPayload>({ ...EMPTY })
const errors = ref<FieldErrors>({})

watch(
  () => [props.open, props.ticket] as const,
  ([open, ticket]) => {
    if (!open) return
    errors.value = {}
    Object.assign(
      formState,
      ticket
        ? {
            title: ticket.title,
            content: ticket.content,
            priority: ticket.priority,
            status: ticket.status,
            assignee: ticket.assignee,
          }
        : EMPTY,
    )
  },
  { immediate: true },
)

const options = computed(() =>
  (assignees.data.value ?? []).map((u) => ({
    value: u.id,
    label: `${u.real_name || u.username}（${u.department_name}）`,
  })),
)

/**
 * ⚠️ antdv 的 `Select` 的 `value` 不接受 `null`（只接受 `undefined`），
 *    而后端的 `assignee` 是 `number | null`——「未指派」在 JSON 里是 null。
 *    在边界上显式转一次，而不是把类型放宽成 any。见 AssignModal 的同名注释。
 */
const assigneeValue = computed({
  get: () => formState.assignee ?? undefined,
  set: (v: number | undefined) => {
    formState.assignee = v ?? null
  },
})

const PRIORITY_OPTIONS = [
  { value: 1, label: '低' },
  { value: 2, label: '中' },
  { value: 3, label: '高' },
]
const STATUS_OPTIONS = [
  { value: 'open', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'closed', label: '已关闭' },
]

function onOk() {
  // ⚠️ 只做必填这类**纯体验**校验。业务规则（长度、唯一性…）一律以后端为准，
  //    在前端复制一份的话，后端改了规则前端不知道，用户会被一条早就不存在的
  //    规则拦住——而且这种 bug 没人会去查前端。
  if (!formState.title.trim()) {
    errors.value = { title: '请输入标题' }
    return
  }
  errors.value = {}
  emit('submit', { ...formState })
}

/** 供父组件在提交失败时调用，把后端的字段错误显示出来。 */
function showServerError(err: unknown) {
  const fields = parseServerFieldErrors(err)
  if (fields) errors.value = fields
  else message.error(parseServerDetail(err) ?? '保存失败')
}
defineExpose({ showServerError })
</script>

<template>
  <Modal
    :open="open"
    :title="ticket ? `编辑工单：${ticket.title}` : '新建工单'"
    :confirm-loading="confirmLoading"
    destroy-on-close
    @cancel="emit('cancel')"
    @ok="onOk"
  >
    <Form layout="vertical">
      <FormItem
        label="标题"
        required
        :help="errors.title"
        :validate-status="errors.title ? 'error' : undefined"
      >
        <Input v-model:value="formState.title" />
      </FormItem>
      <FormItem
        label="内容"
        :help="errors.content"
        :validate-status="errors.content ? 'error' : undefined"
      >
        <Textarea v-model:value="formState.content" :rows="4" />
      </FormItem>
      <FormItem label="优先级">
        <Select v-model:value="formState.priority" :options="PRIORITY_OPTIONS" />
      </FormItem>
      <FormItem label="状态">
        <Select v-model:value="formState.status" :options="STATUS_OPTIONS" />
      </FormItem>
      <FormItem label="处理人">
        <!--
          ⚠️ 候选人来自 /tickets/assignable-users/，只含**你数据范围内**的人。
             不是「全部用户」——那样一个没有 system:user:view 的人
             就通过这个下拉框看到了公司完整的用户名册。
             后端 v0.15.0 的模板表单曾经就是这么写的，fe-v0.11.0 才发现。
        -->
        <Select
          v-model:value="assigneeValue"
          allow-clear
          :loading="assignees.isLoading.value"
          placeholder="未指派"
          :options="options"
        />
      </FormItem>
    </Form>
  </Modal>
</template>
