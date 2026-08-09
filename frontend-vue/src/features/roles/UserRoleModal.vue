<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { Alert, App as AntdApp, Checkbox, CheckboxGroup, Modal } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'

import { fetchUserRoles, saveUserRoles, type AdminUser } from '@/api/admin'

const props = defineProps<{ user: AdminUser | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const { message } = AntdApp.useApp()
const checked = ref<number[]>([])
const saving = ref(false)

const query = useQuery({
  queryKey: computed(() => ['user-roles', props.user?.id]),
  queryFn: () => fetchUserRoles(props.user!.id),
  enabled: computed(() => props.user !== null),
})

/*
 * 🟡 与 React 版的一处形态差异，值得一提。
 *
 *    React 版把「把 checked 同步进本地 state」写在了 `queryFn` **里面**：
 *
 *        queryFn: async () => { const d = await fetchUserRoles(...); setChecked(d.checked); return d }
 *
 *    那是**在数据获取函数里做副作用**——能用，但 queryFn 本该是纯的：
 *    重试、后台刷新、缓存命中时它的调用次数是 Query 说了算的。
 *
 *    Vue 这里用 watch，副作用和获取分开。
 *    ⚠️ 这不是「Vue 更好」——React 版同样可以用 useEffect（它在别处就是这么做的）。
 *       记下来是因为：**两个实现里同一件事写法不一致，说明其中一处是随手写的。**
 */
watch(query.data, (data) => {
  if (data) checked.value = [...data.checked]
})

const ungrantable = computed(() =>
  (query.data.value?.roles ?? []).filter((r) => !r.grantable),
)

async function onOk() {
  if (!props.user) return
  saving.value = true
  try {
    const res = await saveUserRoles(props.user.id, checked.value)
    if (res.rejected > 0) {
      // ADR-011：不能把自己不具备的角色授予他人。
      // 静默丢弃会让管理员以为分配成功了。
      message.warning(
        `已分配 ${res.saved} 个；忽略了 ${res.rejected} 个超出你自身权限范围的角色`,
      )
    } else {
      message.success(`已分配 ${res.saved} 个角色`)
    }
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Modal
    :open="user !== null"
    :title="`分配角色：${user?.username ?? ''}`"
    :confirm-loading="saving"
    destroy-on-close
    @cancel="emit('close')"
    @ok="onOk"
  >
    <Alert
      v-if="ungrantable.length > 0"
      type="warning"
      show-icon
      style="margin-bottom: 12px"
      message="有些角色你授不出去"
      description="灰色的角色包含你自己不具备的权限。权限不可放大（ADR-011）——否则任何人都能通过「造一个更大的角色再给自己」来提权。"
    />
    <CheckboxGroup
      v-model:value="checked"
      style="display: flex; flex-direction: column; gap: 8px"
    >
      <Checkbox
        v-for="r in query.data.value?.roles ?? []"
        :key="r.id"
        :value="r.id"
        :disabled="!r.grantable"
      >
        <!--
          ⚠️ grantable 由后端的 can_grant_role 算，**前端不重算**。
             重算就是把 ADR-011 的规则抄第二遍，两份迟早不一致。
        -->
        {{ r.name }}
        <span style="color: #bfbfbf; margin-left: 8px; font-size: 12px">{{ r.code }}</span>
      </Checkbox>
    </CheckboxGroup>
  </Modal>
</template>
