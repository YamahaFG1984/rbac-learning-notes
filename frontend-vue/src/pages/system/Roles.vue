<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  App as AntdApp,
  Button,
  Form,
  FormItem,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Textarea,
} from 'ant-design-vue'
import { computed, reactive, ref } from 'vue'

import {
  createRole,
  deleteRole,
  fetchRoles,
  updateRole,
  type Role,
  type RolePayload,
} from '@/api/admin'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import RoleDataScope from '@/features/roles/RoleDataScope.vue'
import RolePermTree from '@/features/roles/RolePermTree.vue'
import PageContainer from '@/layouts/PageContainer.vue'
import { parseServerDetail, parseServerFieldErrors, type FieldErrors } from '@/utils/formErrors'

const { message, modal } = AntdApp.useApp()
const queryClient = useQueryClient()

const editing = ref<Role | null | undefined>(undefined)
const permTarget = ref<Role | null>(null)
const scopeTarget = ref<Role | null>(null)

const query = useQuery({ queryKey: computed(() => ['roles']), queryFn: fetchRoles })
const invalidate = () => void queryClient.invalidateQueries({ queryKey: ['roles'] })

const formState = reactive<RolePayload>({
  code: '',
  name: '',
  description: '',
  inherits_from: null,
  order_num: 0,
  is_active: true,
})
const errors = ref<FieldErrors>({})

const save = useMutation({
  mutationFn: (payload: RolePayload) =>
    editing.value ? updateRole(editing.value.id, payload) : createRole(payload),
  onSuccess: () => {
    message.success('已保存')
    invalidate()
    editing.value = undefined
  },
})

const remove = useMutation({
  mutationFn: deleteRole,
  onSuccess: () => {
    message.success('已删除')
    invalidate()
  },
  // 后端可能因为「有用户在用这个角色」而拒绝——把它的话原样显示
  onError: (err: unknown) => message.error(parseServerDetail(err) ?? '删除失败'),
})

function openForm(role: Role | null) {
  editing.value = role
  errors.value = {}
  Object.assign(
    formState,
    role
      ? {
          code: role.code,
          name: role.name,
          description: role.description,
          inherits_from: role.inherits_from,
          order_num: role.order_num,
          is_active: role.is_active,
        }
      : {
          code: '',
          name: '',
          description: '',
          inherits_from: null,
          order_num: 0,
          is_active: true,
        },
  )
}

async function onOk() {
  if (!formState.code.trim() || !formState.name.trim()) {
    errors.value = {
      ...(formState.code.trim() ? {} : { code: '请输入角色编码' }),
      ...(formState.name.trim() ? {} : { name: '请输入角色名称' }),
    }
    return
  }
  errors.value = {}
  try {
    await save.mutateAsync({ ...formState })
  } catch (err) {
    const fields = parseServerFieldErrors(err)
    if (fields) errors.value = fields
    else message.error(parseServerDetail(err) ?? '保存失败')
  }
}

const inheritOptions = computed(() =>
  (query.data.value ?? [])
    .filter((r) => r.id !== editing.value?.id)
    .map((r) => ({ value: r.id, label: r.name })),
)

const inheritValue = computed({
  get: () => formState.inherits_from ?? undefined,
  set: (v: number | undefined) => {
    formState.inherits_from = v ?? null
  },
})

function confirmRemove(row: Role) {
  modal.confirm({
    title: '确认删除？',
    content: `角色「${row.name}」将被删除。`,
    okType: 'danger',
    okText: '确定',
    cancelText: '取消',
    onOk: () => remove.mutateAsync(row.id),
  })
}

const columns = [
  { title: '编码', dataIndex: 'code', width: 140 },
  { title: '名称', dataIndex: 'name', width: 140 },
  { title: '继承自', dataIndex: 'inherits_from_name', key: 'inherits_from_name', width: 120 },
  { title: '数据范围', dataIndex: 'data_scope_display', width: 130 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '操作', key: 'action' },
]
</script>

<template>
  <PageContainer title="角色管理">
    <template #extra>
      <Can :perm="PERM.SYSTEM_ROLE_CREATE">
        <Button type="primary" @click="openForm(null)">新建角色</Button>
      </Can>
    </template>

    <Table
      row-key="id"
      :loading="query.isFetching.value"
      :data-source="query.data.value ?? []"
      :columns="columns"
      :pagination="false"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'inherits_from_name'">
          {{ (record as Role).inherits_from_name || '—' }}
        </template>
        <template v-else-if="column.key === 'is_active'">
          <Tag v-if="(record as Role).is_active" color="green">启用</Tag>
          <Tag v-else>停用</Tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <Space :size="4">
            <Can :perm="PERM.SYSTEM_ROLE_UPDATE">
              <Button type="link" size="small" @click="openForm(record as Role)">
                编辑
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_ROLE_ASSIGN_PERM">
              <Button type="link" size="small" @click="permTarget = record as Role">
                配置权限
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_ROLE_ASSIGN_PERM">
              <Button type="link" size="small" @click="scopeTarget = record as Role">
                数据范围
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_ROLE_DELETE">
              <!-- 内置角色不给删 —— 后端也会拒，这里只是别让人白点一次 -->
              <Button
                type="link"
                size="small"
                danger
                :disabled="(record as Role).is_builtin"
                @click="confirmRemove(record as Role)"
              >
                删除
              </Button>
            </Can>
          </Space>
        </template>
      </template>
    </Table>

    <Modal
      :open="editing !== undefined"
      :title="editing ? `编辑角色：${editing.name}` : '新建角色'"
      :confirm-loading="save.isPending.value"
      destroy-on-close
      @cancel="editing = undefined"
      @ok="onOk"
    >
      <Form layout="vertical">
        <FormItem
          label="角色编码"
          required
          :help="errors.code"
          :validate-status="errors.code ? 'error' : undefined"
        >
          <Input v-model:value="formState.code" :disabled="!!editing" placeholder="如 cs_manager" />
        </FormItem>
        <FormItem
          label="角色名称"
          required
          :help="errors.name"
          :validate-status="errors.name ? 'error' : undefined"
        >
          <Input v-model:value="formState.name" />
        </FormItem>
        <FormItem label="描述">
          <Textarea v-model:value="formState.description" :rows="2" />
        </FormItem>
        <!--
          ⚠️ 语义固定为 child ⊇ parent：选了谁，本角色就拥有谁的全部权限。
             字段名叫 inherits_from 而不是 parent，就是为了让这句话只有一种读法。
        -->
        <FormItem
          label="继承自"
          extra="本角色将自动拥有所选角色的全部权限。环、超过 5 层的继承由后端拒绝。"
        >
          <Select
            v-model:value="inheritValue"
            allow-clear
            placeholder="不继承"
            :options="inheritOptions"
          />
        </FormItem>
        <FormItem label="排序">
          <InputNumber v-model:value="formState.order_num" :min="0" />
        </FormItem>
        <FormItem label="启用">
          <Switch v-model:checked="formState.is_active" />
        </FormItem>
      </Form>
    </Modal>

    <RolePermTree :role="permTarget" @close="permTarget = null" @saved="invalidate" />
    <RoleDataScope :role="scopeTarget" @close="scopeTarget = null" @saved="invalidate" />
  </PageContainer>
</template>
