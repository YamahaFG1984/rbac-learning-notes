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
} from 'ant-design-vue'
import { computed, reactive, ref } from 'vue'

import {
  createDepartment,
  deleteDepartment,
  fetchDepartments,
  updateDepartment,
  type Department,
  type DepartmentPayload,
} from '@/api/admin'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import PageContainer from '@/layouts/PageContainer.vue'
import { parseServerDetail, parseServerFieldErrors, type FieldErrors } from '@/utils/formErrors'

interface TreeRow extends Department {
  children?: TreeRow[]
}

/**
 * ⚠️ 用后端给的 `parent` 关系在前端组树，**不靠 `path` 字符串排序**。
 *
 *    后端 v0.4.0 踩过这个坑：`ORDER BY path` 不是先序遍历——
 *    path 是字符串，`/2/6/10/` 排在 `/2/6/7/` 前面，而且它忽略 `order_num`。
 *    同级排序必须显式按 `order_num`。
 *
 * 🟢 本函数与 React 版**逐字相同**（纯函数）。
 */
function buildTree(rows: Department[]): TreeRow[] {
  const byParent = new Map<number | null, Department[]>()
  for (const d of rows) {
    const list = byParent.get(d.parent) ?? []
    list.push(d)
    byParent.set(d.parent, list)
  }
  for (const list of byParent.values()) {
    list.sort((a, b) => a.order_num - b.order_num || a.id - b.id)
  }
  const build = (parent: number | null): TreeRow[] =>
    (byParent.get(parent) ?? []).map((d) => {
      const children = build(d.id)
      return children.length > 0 ? { ...d, children } : { ...d }
    })
  return build(null)
}

const { message, modal } = AntdApp.useApp()
const queryClient = useQueryClient()

const query = useQuery({
  queryKey: computed(() => ['departments']),
  queryFn: fetchDepartments,
})
const invalidate = () => void queryClient.invalidateQueries({ queryKey: ['departments'] })

const tree = computed(() => buildTree(query.data.value ?? []))

/** `undefined` = 弹窗关闭；`null` = 新建；有值 = 编辑 */
const editing = ref<Department | null | undefined>(undefined)
const formState = reactive<DepartmentPayload>({
  code: '',
  name: '',
  parent: null,
  order_num: 0,
  is_active: true,
})
const errors = ref<FieldErrors>({})

const save = useMutation({
  mutationFn: (payload: DepartmentPayload) =>
    editing.value ? updateDepartment(editing.value.id, payload) : createDepartment(payload),
  onSuccess: () => {
    message.success('已保存')
    invalidate()
    editing.value = undefined
  },
})

const remove = useMutation({
  mutationFn: deleteDepartment,
  onSuccess: () => {
    message.success('已删除')
    invalidate()
  },
  onError: (err: unknown) => {
    /*
     * ⚠️ 部门的 `parent` 和 `user.department` 都是 `PROTECT`。
     *    有子部门或有人在里面时删除会被数据库拒绝——
     *    把后端的话原样显示出来，不要自己编一句「删除失败」。
     *
     *    用数据库约束表达业务规则，比在 `delete()` 里写检查更难被绕过。
     */
    message.error(parseServerDetail(err) ?? '删除失败：该部门可能有下级或成员')
  },
})

function openForm(dept: Department | null, parent: number | null = null) {
  editing.value = dept
  errors.value = {}
  Object.assign(
    formState,
    dept
      ? {
          code: dept.code,
          name: dept.name,
          parent: dept.parent,
          order_num: dept.order_num,
          is_active: dept.is_active,
        }
      : { code: '', name: '', parent, order_num: 0, is_active: true },
  )
}

async function onOk() {
  if (!formState.name.trim() || !formState.code.trim()) {
    errors.value = {
      ...(formState.name.trim() ? {} : { name: '请输入部门名称' }),
      ...(formState.code.trim() ? {} : { code: '请输入部门编码' }),
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

const parentOptions = computed(() =>
  (query.data.value ?? [])
    .filter((d) => d.id !== editing.value?.id)
    .map((d) => ({ value: d.id, label: d.name })),
)

// antdv 的 Select 不接受 null（同 vue-v0.9.0 的 assignee），边界转一次
const parentValue = computed({
  get: () => formState.parent ?? undefined,
  set: (v: number | undefined) => {
    formState.parent = v ?? null
  },
})

function confirmRemove(row: TreeRow) {
  modal.confirm({
    title: '确认删除？',
    content: `部门「${row.name}」将被删除。有下级或成员时会被拒绝。`,
    okType: 'danger',
    okText: '确定',
    cancelText: '取消',
    onOk: () => remove.mutateAsync(row.id),
  })
}

/**
 * 🔴📌 `defaultExpandAllRows` 在**数据异步到达**时不生效（vue-v0.10.0 实测）。
 *
 *    它只在首次渲染时计算一次「默认展开哪些行」，而那时 `dataSource` 还是空数组
 *    （数据来自 useQuery）。数据回来之后默认值不会重算。
 *
 *    表现：树形表格只显示**顶层节点**——权限点 26 个只显示 4 个、
 *    部门 6 个只显示 1 个。**不报错，看起来就像「设计成折叠的」。**
 *
 *    ⚠️ **React 版有一模一样的 bug**（实测：同样是 4 行和 1 行）。
 *       这不是 Vue/React 差异，是 antd/antdv 共有的行为，
 *       而 fe-v0.12.0 的 92 个 E2E 没有断言过行数，所以一直没被发现。
 *       本项目只修 Vue 版（frontend/ 要保持 fe-v1.0.0 原样以供对比），
 *       该发现记在 04 对比文档与本 tag 规格书里。
 *
 *    修法：自己算出全部有子节点的 key，用受控的 expandedRowKeys。
 */
const expandedRowKeys = computed(() => {
  const keys: number[] = []
  const walk = (rows: TreeRow[]) => {
    for (const r of rows) {
      if (r.children?.length) {
        keys.push(r.id)
        walk(r.children)
      }
    }
  }
  walk(tree.value)
  return keys
})

const columns = [
  { title: '名称', dataIndex: 'name' },
  { title: '编码', dataIndex: 'code', width: 120 },
  { title: '排序', dataIndex: 'order_num', width: 80 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '操作', key: 'action', width: 200 },
]
</script>

<template>
  <PageContainer title="部门管理">
    <template #extra>
      <Can :perm="PERM.SYSTEM_DEPT_CREATE">
        <Button type="primary" @click="openForm(null)">新建部门</Button>
      </Can>
    </template>

    <Table
      row-key="id"
      :loading="query.isFetching.value"
      :data-source="tree"
      :columns="columns"
      :pagination="false"
      :expanded-row-keys="expandedRowKeys"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_active'">
          <Tag v-if="(record as TreeRow).is_active" color="green">启用</Tag>
          <Tag v-else>停用</Tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <Space :size="4">
            <Can :perm="PERM.SYSTEM_DEPT_CREATE">
              <Button type="link" size="small" @click="openForm(null, (record as TreeRow).id)">
                加下级
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_DEPT_UPDATE">
              <Button type="link" size="small" @click="openForm(record as TreeRow)">
                编辑
              </Button>
            </Can>
            <Can :perm="PERM.SYSTEM_DEPT_DELETE">
              <Button
                type="link"
                size="small"
                danger
                @click="confirmRemove(record as TreeRow)"
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
      :title="editing ? `编辑部门：${editing.name}` : '新建部门'"
      :confirm-loading="save.isPending.value"
      destroy-on-close
      @cancel="editing = undefined"
      @ok="onOk"
    >
      <Form layout="vertical">
        <FormItem
          label="部门名称"
          required
          :help="errors.name"
          :validate-status="errors.name ? 'error' : undefined"
        >
          <Input v-model:value="formState.name" />
        </FormItem>
        <FormItem
          label="部门编码"
          required
          :help="errors.code"
          :validate-status="errors.code ? 'error' : undefined"
        >
          <Input v-model:value="formState.code" :disabled="!!editing" />
        </FormItem>
        <FormItem
          label="上级部门"
          extra="留空表示顶级部门。path / depth 由后端维护，前端不提交。"
        >
          <Select
            v-model:value="parentValue"
            allow-clear
            placeholder="顶级部门"
            :options="parentOptions"
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
  </PageContainer>
</template>
