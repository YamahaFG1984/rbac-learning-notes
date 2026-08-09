<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { Alert, App as AntdApp, Modal, RadioGroup, Spin, Tree } from 'ant-design-vue'
import type { TreeProps } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'

import { fetchDataScope, saveDataScope, type Role } from '@/api/admin'

const props = defineProps<{ role: Role | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const { message } = AntdApp.useApp()
const scope = ref<number | null>(null)
const checkedKeys = ref<number[]>([])
const saving = ref(false)

const query = useQuery({
  queryKey: computed(() => ['role-data-scope', props.role?.id]),
  queryFn: () => fetchDataScope(props.role!.id),
  enabled: computed(() => props.role !== null),
})

watch(query.data, (data) => {
  if (!data) return
  scope.value = data.dataScope
  checkedKeys.value = data.departments.filter((d) => d.checked).map((d) => d.id)
})

const treeData = computed<TreeProps['treeData']>(() => {
  const depts = query.data.value?.departments
  if (!depts) return []
  const byParent = new Map<number | null, typeof depts>()
  for (const d of depts) {
    const list = byParent.get(d.parent) ?? []
    list.push(d)
    byParent.set(d.parent, list)
  }
  const build = (parent: number | null): NonNullable<TreeProps['treeData']> =>
    (byParent.get(parent) ?? []).map((d) => ({
      key: d.id,
      title: d.name,
      children: build(d.id),
    }))
  return build(null)
})

const isCustom = computed(() => scope.value === query.data.value?.customValue)

const scopeOptions = computed(() =>
  (query.data.value?.scopes ?? []).map((s) => ({ value: s.value, label: s.label })),
)

async function handleSave() {
  if (!props.role || scope.value === null) return
  saving.value = true
  try {
    /*
     * ⚠️ 只提交用户勾了哪几个部门，**不展开子树**。
     *
     *    后端 `get_role_custom_dept_ids()` 在查询时才展开。
     *    前端提前展开的话，将来新增的子部门永远进不了这个范围——
     *    而管理员勾「客服部」时的意图几乎肯定包含「以后新建的下级」。
     *
     * ⚠️ 这个接口走后端的 `save_role_scope()`，它负责发 `role_scope_changed`
     *    信号 → 写审计日志。fe-v0.12.0 挖出过「改数据范围完全没有审计」
     *    （AuditAction.ROLE_SCOPE_SET 定义了却没人发出），后端已修。
     */
    await saveDataScope(props.role.id, scope.value, isCustom.value ? checkedKeys.value : [])
    message.success('数据范围已更新')
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}

function onCheck(keys: unknown) {
  const value = Array.isArray(keys) ? keys : (keys as { checked: number[] }).checked
  checkedKeys.value = value as number[]
}
</script>

<template>
  <Modal
    :open="role !== null"
    :title="`数据范围：${role?.name ?? ''}`"
    :width="560"
    :confirm-loading="saving"
    destroy-on-close
    @cancel="emit('close')"
    @ok="handleSave"
  >
    <Spin v-if="query.isLoading.value || scope === null" />
    <template v-else>
      <RadioGroup
        v-model:value="scope"
        style="display: flex; flex-direction: column; gap: 8px"
        :options="scopeOptions"
      />

      <div v-if="isCustom" style="margin-top: 16px">
        <Alert
          type="info"
          show-icon
          style="margin-bottom: 12px"
          message="勾选的部门包含其所有下级"
          description="以后在这些部门下新建的子部门会自动包含进来，不需要回来补勾。"
        />
        <!--
          这里同样用 checkStrictly：勾「客服部」就只提交客服部，
          展开子树是后端的事。让联动自动勾上三个子部门的话，
          提交的就变成 4 个 id，新增子部门后不会自动包含。
        -->
        <Tree
          checkable
          check-strictly
          :tree-data="treeData"
          default-expand-all
          :checked-keys="{ checked: checkedKeys, halfChecked: [] }"
          @check="onCheck"
        />
      </div>
    </template>
  </Modal>
</template>
