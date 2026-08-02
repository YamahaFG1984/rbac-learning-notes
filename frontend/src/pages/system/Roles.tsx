import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag } from 'antd'

import {
  createRole,
  deleteRole,
  fetchRoles,
  updateRole,
  type Role,
  type RolePayload,
} from '@/api/admin'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'
import { RoleDataScope } from '@/features/roles/RoleDataScope'
import { RolePermTree } from '@/features/roles/RolePermTree'
import { PageContainer } from '@/layouts/PageContainer'
import { applyServerFieldErrors } from '@/utils/formErrors'

export default function Roles() {
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<RolePayload>()

  const [editing, setEditing] = useState<Role | null | undefined>(undefined)
  const [permTarget, setPermTarget] = useState<Role | null>(null)
  const [scopeTarget, setScopeTarget] = useState<Role | null>(null)

  const query = useQuery({ queryKey: ['roles'], queryFn: fetchRoles })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['roles'] })

  const save = useMutation({
    mutationFn: (payload: RolePayload) =>
      editing ? updateRole(editing.id, payload) : createRole(payload),
    onSuccess: () => {
      message.success('已保存')
      invalidate()
      setEditing(undefined)
    },
  })

  const remove = useMutation({
    mutationFn: deleteRole,
    onSuccess: () => {
      message.success('已删除')
      invalidate()
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      // 后端可能因为「有用户在用这个角色」而拒绝——把它的话原样显示
      message.error(err.response?.data?.detail ?? '删除失败')
    },
  })

  const openForm = (role: Role | null) => {
    setEditing(role)
    form.setFieldsValue(
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

  return (
    <PageContainer
      title="角色管理"
      extra={
        <Can perm={PERM.SYSTEM_ROLE_CREATE}>
          <Button type="primary" onClick={() => openForm(null)}>
            新建角色
          </Button>
        </Can>
      }
    >
      <Table<Role>
        rowKey="id"
        loading={query.isFetching}
        dataSource={query.data ?? []}
        pagination={false}
        columns={[
          { title: '编码', dataIndex: 'code', width: 140 },
          { title: '名称', dataIndex: 'name', width: 140 },
          {
            title: '继承自',
            dataIndex: 'inherits_from_name',
            width: 120,
            render: (v: string) => v || '—',
          },
          { title: '数据范围', dataIndex: 'data_scope_display', width: 130 },
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
            render: (_, row) => (
              <Space size={4}>
                <Can perm={PERM.SYSTEM_ROLE_UPDATE}>
                  <Button type="link" size="small" onClick={() => openForm(row)}>
                    编辑
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_ROLE_ASSIGN_PERM}>
                  <Button type="link" size="small" onClick={() => setPermTarget(row)}>
                    配置权限
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_ROLE_ASSIGN_PERM}>
                  <Button type="link" size="small" onClick={() => setScopeTarget(row)}>
                    数据范围
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_ROLE_DELETE}>
                  <Button
                    type="link"
                    size="small"
                    danger
                    /* 内置角色不给删 —— 后端也会拒，这里只是别让人白点一次 */
                    disabled={row.is_builtin}
                    onClick={() =>
                      modal.confirm({
                        title: '确认删除？',
                        content: `角色「${row.name}」将被删除。`,
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
        title={editing ? `编辑角色：${editing.name}` : '新建角色'}
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
          <Form.Item name="code" label="角色编码" rules={[{ required: true }]}>
            <Input disabled={!!editing} placeholder="如 cs_manager" />
          </Form.Item>
          <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="inherits_from"
            label="继承自"
            /*
             * ⚠️ 语义固定为 child ⊇ parent：选了谁，本角色就拥有谁的全部权限。
             *    字段名叫 inherits_from 而不是 parent，就是为了让这句话只有一种读法。
             */
            extra="本角色将自动拥有所选角色的全部权限。环、超过 5 层的继承由后端拒绝。"
          >
            <Select
              allowClear
              placeholder="不继承"
              options={(query.data ?? [])
                .filter((r) => r.id !== editing?.id)
                .map((r) => ({ value: r.id, label: r.name }))}
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

      <RolePermTree
        role={permTarget}
        onClose={() => setPermTarget(null)}
        onSaved={invalidate}
      />
      <RoleDataScope
        role={scopeTarget}
        onClose={() => setScopeTarget(null)}
        onSaved={invalidate}
      />
    </PageContainer>
  )
}
