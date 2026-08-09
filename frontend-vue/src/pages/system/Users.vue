<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  App as AntdApp,
  Button,
  Form,
  FormItem,
  Input,
  InputSearch,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
} from 'ant-design-vue'
import { computed, reactive, ref } from 'vue'

import {
  createUser,
  deleteUser,
  fetchDepartments,
  fetchUsers,
  updateUser,
  type AdminUser,
  type UserPayload,
} from '@/api/admin'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import UserRoleModal from '@/features/roles/UserRoleModal.vue'
import { useTableQuery } from '@/hooks/useTableQuery'
import PageContainer from '@/layouts/PageContainer.vue'
import { parseServerDetail, parseServerFieldErrors, type FieldErrors } from '@/utils/formErrors'

type UserQuery = { page: number; kw: string }
const DEFAULTS: UserQuery = { page: 1, kw: '' }

const { message, modal } = AntdApp.useApp()
const queryClient = useQueryClient()

const { params, setParams } = useTableQuery(DEFAULTS)
const editing = ref<AdminUser | null | undefined>(undefined)
const roleTarget = ref<AdminUser | null>(null)

const query = useQuery({
  queryKey: computed(() => ['users', params.value]),
  queryFn: () => fetchUsers(params.value),
})
const depts = useQuery({
  queryKey: computed(() => ['departments']),
  queryFn: fetchDepartments,
})
const invalidate = () => void queryClient.invalidateQueries({ queryKey: ['users'] })

const formState = reactive<UserPayload>({
  username: '',
  real_name: '',
  phone: '',
  email: '',
  department: null,
  is_active: true,
})
const errors = ref<FieldErrors>({})

const save = useMutation({
  mutationFn: (payload: UserPayload) =>
    editing.value ? updateUser(editing.value.id, payload) : createUser(payload),
  onSuccess: () => {
    message.success('已保存')
    invalidate()
    editing.value = undefined
  },
})

const remove = useMutation({
  mutationFn: deleteUser,
  onSuccess: () => {
    message.success('已删除')
    invalidate()
  },
  onError: (err: unknown) =>
    message.error(parseServerDetail(err) ?? '删除失败：该用户可能有关联数据'),
})

function openForm(user: AdminUser | null) {
  editing.value = user
  errors.value = {}
  Object.assign(
    formState,
    user
      ? {
          username: user.username,
          real_name: user.real_name,
          phone: user.phone,
          email: user.email,
          department: user.department,
          is_active: user.is_active,
        }
      : {
          username: '',
          real_name: '',
          phone: '',
          email: '',
          department: null,
          is_active: true,
        },
  )
}

async function onOk() {
  if (!formState.username.trim()) {
    errors.value = { username: '请输入用户名' }
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

const deptOptions = computed(() =>
  (depts.data.value ?? []).map((d) => ({ value: d.id, label: d.name })),
)
const deptValue = computed({
  get: () => formState.department ?? undefined,
  set: (v: number | undefined) => {
    formState.department = v ?? null
  },
})

function confirmRemove(row: AdminUser) {
  modal.confirm({
    title: '确认删除？',
    content: `用户「${row.username}」将被删除。`,
    okType: 'danger',
    okText: '确定',
    cancelText: '取消',
    onOk: () => remove.mutateAsync(row.id),
  })
}

const pagination = computed(() => ({
  current: params.value.page,
  total: query.data.value?.count ?? 0,
  pageSize: 20,
  showTotal: (t: number) => `共 ${t} 条`,
  showSizeChanger: false,
}))

const columns = [
  { title: '用户名', dataIndex: 'username', width: 130 },
  { title: '姓名', dataIndex: 'real_name', width: 120 },
  { title: '部门', dataIndex: 'department_name', key: 'department_name', width: 130 },
  { title: '手机号', dataIndex: 'phone', width: 130 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '操作', key: 'action', width: 230 },
]
</script>

<template>
  <PageContainer title="用户管理">
    <template #extra>
      <Can :perm="PERM.SYSTEM_USER_CREATE">
        <Button type="primary" @click="openForm(null)">新建用户</Button>
      </Can>
    </template>

    <InputSearch
      placeholder="搜索用户名或姓名"
      allow-clear
      :default-value="params.kw"
      style="width: 240px; margin-bottom: 16px"
      @search="(kw: string) => setParams({ kw, page: 1 })"
    />

    <Table
      row-key="id"
      :loading="query.isFetching.value"
      :data-source="query.data.value?.results ?? []"
      :columns="columns"
      :pagination="pagination"
      @change="(p: { current?: number }) => setParams({ page: p.current ?? 1 })"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'department_name'">
          {{ (record as AdminUser).department_name || '—' }}
        </template>
        <template v-else-if="column.key === 'is_active'">
          <Tag v-if="(record as AdminUser).is_active" color="green">启用</Tag>
          <Tag v-else>停用</Tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <Space :size="4">
            <Can :perm="PERM.SYSTEM_USER_UPDATE">
              <Button type="link" size="small" @click="openForm(record as AdminUser)">
                编辑
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_USER_ASSIGN_ROLE">
              <Button type="link" size="small" @click="roleTarget = record as AdminUser">
                分配角色
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_USER_DELETE">
              <Button
                type="link"
                size="small"
                danger
                @click="confirmRemove(record as AdminUser)"
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
      :title="editing ? `编辑用户：${editing.username}` : '新建用户'"
      :confirm-loading="save.isPending.value"
      destroy-on-close
      @cancel="editing = undefined"
      @ok="onOk"
    >
      <!--
        🔴 这个表单里**没有** is_superuser，也没有密码字段。

           安全红线 4：超管只能通过 createsuperuser 创建。
           表单里出现这个字段的话，任何有 system:user:update 权限的人
           都能把自己变成超管——**一次点击完成提权**。

           后端的 serializer 白名单也没有它，但前端不该依赖那一点：
           「不要把安全性寄托在对端的实现细节上」。
      -->
      <Form layout="vertical">
        <FormItem
          label="用户名"
          required
          :help="errors.username"
          :validate-status="errors.username ? 'error' : undefined"
        >
          <Input v-model:value="formState.username" :disabled="!!editing" />
        </FormItem>
        <FormItem label="姓名">
          <Input v-model:value="formState.real_name" />
        </FormItem>
        <FormItem label="所属部门">
          <Select
            v-model:value="deptValue"
            allow-clear
            placeholder="未分配"
            :options="deptOptions"
          />
        </FormItem>
        <FormItem
          label="手机号"
          :help="errors.phone"
          :validate-status="errors.phone ? 'error' : undefined"
        >
          <Input v-model:value="formState.phone" />
        </FormItem>
        <FormItem
          label="邮箱"
          :help="errors.email"
          :validate-status="errors.email ? 'error' : undefined"
        >
          <Input v-model:value="formState.email" />
        </FormItem>
        <FormItem label="启用">
          <Switch v-model:checked="formState.is_active" />
        </FormItem>
      </Form>
    </Modal>

    <UserRoleModal :user="roleTarget" @close="roleTarget = null" @saved="invalidate" />
  </PageContainer>
</template>
