import { useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag } from 'antd'

import {
  createDepartment,
  deleteDepartment,
  fetchDepartments,
  updateDepartment,
  type Department,
  type DepartmentPayload,
} from '@/api/admin'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'
import { PageContainer } from '@/layouts/PageContainer'
import { applyServerFieldErrors } from '@/utils/formErrors'

interface TreeRow extends Department {
  children?: TreeRow[]
}

/**
 * ⚠️ 用后端给的 parent 关系在前端组树，不靠 path 字符串排序。
 *
 *    后端 v0.4.0 踩过这个坑：`ORDER BY path` 不是先序遍历——
 *    path 是字符串，"/2/6/10/" 排在 "/2/6/7/" 前面，而且它忽略 order_num。
 *    同级排序必须显式按 order_num。
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

export default function Departments() {
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<DepartmentPayload>()
  const [editing, setEditing] = useState<Department | null | undefined>(undefined)

  const query = useQuery({ queryKey: ['departments'], queryFn: fetchDepartments })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['departments'] })

  const tree = useMemo(() => buildTree(query.data ?? []), [query.data])

  const save = useMutation({
    mutationFn: (payload: DepartmentPayload) =>
      editing ? updateDepartment(editing.id, payload) : createDepartment(payload),
    onSuccess: () => {
      message.success('已保存')
      invalidate()
      setEditing(undefined)
    },
  })

  const remove = useMutation({
    mutationFn: deleteDepartment,
    onSuccess: () => {
      message.success('已删除')
      invalidate()
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      /*
       * ⚠️ 部门的 parent 和 user.department 都是 PROTECT。
       *    有子部门或有人在里面时删除会被数据库拒绝——
       *    把后端的话原样显示出来，不要自己编一句「删除失败」。
       *
       *    用数据库约束表达业务规则，比在 delete() 里写检查更难被绕过。
       */
      message.error(err.response?.data?.detail ?? '删除失败：该部门可能有下级或成员')
    },
  })

  const openForm = (dept: Department | null, parent: number | null = null) => {
    setEditing(dept)
    form.setFieldsValue(
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

  return (
    <PageContainer
      title="部门管理"
      extra={
        <Can perm={PERM.SYSTEM_DEPT_CREATE}>
          <Button type="primary" onClick={() => openForm(null)}>
            新建部门
          </Button>
        </Can>
      }
    >
      <Table<TreeRow>
        rowKey="id"
        loading={query.isFetching}
        dataSource={tree}
        pagination={false}
        defaultExpandAllRows
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '编码', dataIndex: 'code', width: 120 },
          { title: '排序', dataIndex: 'order_num', width: 80 },
          {
            title: '状态',
            dataIndex: 'is_active',
            width: 80,
            render: (v: boolean) =>
              v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
          },
          {
            title: '操作',
            key: 'action',
            width: 200,
            render: (_, row) => (
              <Space size={4}>
                <Can perm={PERM.SYSTEM_DEPT_CREATE}>
                  <Button type="link" size="small" onClick={() => openForm(null, row.id)}>
                    加下级
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_DEPT_UPDATE}>
                  <Button type="link" size="small" onClick={() => openForm(row)}>
                    编辑
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_DEPT_DELETE}>
                  <Button
                    type="link"
                    size="small"
                    danger
                    onClick={() =>
                      modal.confirm({
                        title: '确认删除？',
                        content: `部门「${row.name}」将被删除。有下级或成员时会被拒绝。`,
                        okType: 'danger',
                        onOk: () => remove.mutateAsync(row.id),
                      })
                    }
                  >
                    删除
                  </Button>
                </Can>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={editing !== undefined}
        title={editing ? `编辑部门：${editing.name}` : '新建部门'}
        onCancel={() => setEditing(undefined)}
        confirmLoading={save.isPending}
        onOk={async () => {
          const values = await form.validateFields()
          try {
            await save.mutateAsync(values)
          } catch (err) {
            applyServerFieldErrors(form, err)
          }
        }}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="部门名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="部门编码" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item
            name="parent"
            label="上级部门"
            extra="留空表示顶级部门。path / depth 由后端维护，前端不提交。"
          >
            <Select
              allowClear
              placeholder="顶级部门"
              options={(query.data ?? [])
                .filter((d) => d.id !== editing?.id)
                .map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <Form.Item name="order_num" label="排序">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  )
}
