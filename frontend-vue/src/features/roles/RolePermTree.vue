<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { Alert, App as AntdApp, Modal, Spin, Tree } from 'ant-design-vue'
import type { TreeProps } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'

import {
  fetchRolePermissions,
  saveRolePermissions,
  type PermNode,
  type Role,
} from '@/api/admin'

const props = defineProps<{ role: Role | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const { message } = AntdApp.useApp()
const checkedKeys = ref<number[]>([])
const saving = ref(false)

const query = useQuery({
  queryKey: computed(() => ['role-permissions', props.role?.id]),
  queryFn: () => fetchRolePermissions(props.role!.id),
  enabled: computed(() => props.role !== null),
})

watch(query.data, (data) => {
  if (data) checkedKeys.value = data.nodes.filter((n) => n.checked).map((n) => n.id)
})

/**
 * 把扁平的权限节点组装成 Tree 的数据。
 *
 * ⚠️ 纯继承的项设 `disabled` + 灰色标签。
 *    「继承来的权限不能在子角色里取消」——那需要「负权限」，本项目不做。
 *
 * 🟡 与 React 版的差异：React 用 JSX 直接把 `<Tag>继承</Tag>` 拼进 `title`；
 *    Vue 这里把标记放进数据（`inherited`），由模板的 `#title` 插槽渲染。
 *    **数据与呈现分得更开**，代价是要多写一个插槽。
 */
const treeData = computed<TreeProps['treeData']>(() => {
  const nodes = query.data.value?.nodes
  if (!nodes) return []

  const byParent = new Map<number | null, PermNode[]>()
  for (const n of nodes) {
    const list = byParent.get(n.parent) ?? []
    list.push(n)
    byParent.set(n.parent, list)
  }

  const build = (parent: number | null): NonNullable<TreeProps['treeData']> =>
    (byParent.get(parent) ?? []).map((n) => ({
      key: n.id,
      disabled: n.inherited,
      title: n.name,
      code: n.code,
      inherited: n.inherited,
      children: build(n.id),
    }))

  return build(null)
})

async function handleSave() {
  if (!props.role || !query.data.value) return
  saving.value = true
  try {
    /*
     * 🔴 只提交「勾选的」且「不是纯继承的」。
     *
     *    继承来的权限本来就不该出现在提交值里——它属于父角色。
     *    而 disabled 的节点根本进不了 checkedKeys，这里的过滤
     *    是为了防止 checkStrictly 的联动把它们意外带上。
     */
    const inherited = new Set(
      query.data.value.nodes.filter((n) => n.inherited).map((n) => n.id),
    )
    const payload = checkedKeys.value.filter((id) => !inherited.has(id))

    const res = await saveRolePermissions(props.role.id, payload)
    if (res.rejected > 0) {
      // ⚠️ 不能静默丢弃 —— 那会让管理员以为保存成功了（ADR-011）
      message.warning(
        `已保存 ${res.saved} 项；忽略了 ${res.rejected} 项你自己不具备的权限——不能授出自己没有的权限`,
      )
    } else {
      message.success(`已保存 ${res.saved} 项权限`)
    }
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
    :title="`配置权限：${role?.name ?? ''}`"
    :width="640"
    :confirm-loading="saving"
    destroy-on-close
    @cancel="emit('close')"
    @ok="handleSave"
  >
    <Spin v-if="query.isLoading.value" />
    <template v-else>
      <Alert
        v-if="query.data.value?.hasInherited"
        type="info"
        show-icon
        style="margin-bottom: 12px"
        :message="`本角色继承自「${query.data.value.inheritsFromName}」`"
        description="带「继承」标签的权限来自父角色，不可在这里取消。要取消需修改父角色，或解除继承关系。"
      />
      <!--
        🔴 checkStrictly：父子节点的勾选**互不联动**。

           默认的联动会在勾父节点时把子节点一起带上，
           而「哪些 key 会被提交」在权限场景必须是完全可控的——
           多带一个 catalog 下的按钮权限，就是多授出一个操作。

           代价是用户要逐个勾。这在权限配置页是可以接受的交换：
           这个页面一年用不了几次，但每次都事关重大。
           （同模板版 v0.5.0 选择手写联动而不用现成组件。）

        🟢 属性名与 React 版**完全相同**——antd 和 antdv 在这一点上一致。
      -->
      <Tree
        checkable
        check-strictly
        :tree-data="treeData"
        default-expand-all
        :checked-keys="{ checked: checkedKeys, halfChecked: [] }"
        @check="onCheck"
      >
        <template #title="node">
          <span>
            {{ node.title }}
            <span
              v-if="node.code"
              style="color: #bfbfbf; margin-left: 8px; font-size: 12px"
            >
              {{ node.code }}
            </span>
            <span
              v-if="node.inherited"
              class="ant-tag"
              style="margin-left: 8px"
            >
              继承
            </span>
          </span>
        </template>
      </Tree>
    </template>
  </Modal>
</template>
