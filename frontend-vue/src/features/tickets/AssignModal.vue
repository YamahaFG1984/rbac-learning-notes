<script setup lang="ts">
import { App as AntdApp, Form, FormItem, Modal, Select } from 'ant-design-vue'
import { computed, ref, toRef, watch } from 'vue'

import { parseServerDetail, parseServerFieldErrors } from '@/utils/formErrors'

import { useAssignableUsers } from './useTicketMutations'

/**
 * 派单。
 *
 * ⚠️ 候选人列表来自 `/tickets/assignable-users/`，权限点是 `ticket:ticket:assign`。
 *    它**没有**复用 `/api/v1/users/` —— 那个接口要 `system:user:view`，
 *    而 cs_manager 只有派单权限。
 *
 *    如果图省事复用了，结果就是「为了让主管能派单，只好给他用户管理权限」。
 *    **权限点被业务需求倒逼着变粗，是权限模型腐化的典型路径。**
 */
const props = defineProps<{
  open: boolean
  currentAssignee: number | null
  confirmLoading?: boolean
}>()
const emit = defineEmits<{
  cancel: []
  submit: [assignee: number | null]
}>()

// ⚠️ 关着的时候不请求候选人 —— 打开表单才是需要它的时刻。
//    enabled 必须是 ref/computed（V-ADR-009）。
const { message } = AntdApp.useApp()
const assignees = useAssignableUsers(toRef(props, 'open'))

const assignee = ref<number | null>(null)
const fieldError = ref<string | null>(null)

watch(
  () => props.open,
  (open) => {
    if (open) {
      assignee.value = props.currentAssignee
      fieldError.value = null
    }
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
 *
 *    直接绑 `assignee` 会报
 *    `Type 'null' is not assignable to type 'SelectValue'`。
 *
 *    🟡 React 版没有这个问题：antd 的 `Select` 通过 `Form` 传值，
 *       类型是 `any`，null 直接穿过去了。
 *       **代价是 React 那边没有类型检查兜住这个不匹配**——
 *       表现相同（都能用），但 Vue 这边是编译期发现的。
 *
 *    这里显式做一层转换，而不是把类型放宽成 any：
 *    「界面上的空值」和「接口里的空值」本来就该在边界上对齐一次。
 */
const selectValue = computed({
  get: () => assignee.value ?? undefined,
  set: (v: number | undefined) => {
    assignee.value = v ?? null
  },
})

/**
 * 🟡 与 React 版的差异只在最后一步。
 *
 *    React：`applyServerFieldErrors(form, err)` —— antd 的 `form.setFields()`
 *      直接把错误注进表单实例。
 *    Vue：antdv 没有对应的命令式 API，所以解析出来自己驱动
 *      `<FormItem :help :validate-status>`。
 *
 *    **解析逻辑两边相同，是 UI 库能力的差异。**
 */
async function onOk() {
  try {
    emit('submit', assignee.value ?? null)
  } catch (err) {
    const fields = parseServerFieldErrors(err)
    if (fields?.assignee) fieldError.value = fields.assignee
    else message.error(parseServerDetail(err) ?? '派单失败')
  }
}
</script>

<template>
  <Modal
    :open="open"
    title="派单"
    :confirm-loading="confirmLoading"
    destroy-on-close
    @cancel="emit('cancel')"
    @ok="onOk"
  >
    <Form layout="vertical">
      <FormItem
        label="处理人"
        :help="fieldError ?? undefined"
        :validate-status="fieldError ? 'error' : undefined"
      >
        <Select
          v-model:value="selectValue"
          allow-clear
          :loading="assignees.isLoading.value"
          placeholder="未指派"
          :options="options"
        />
      </FormItem>
    </Form>
  </Modal>
</template>
