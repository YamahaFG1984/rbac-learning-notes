import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, App, Button, Checkbox, Form, Input, Modal, Select, Space, Switch, Table, Tag } from 'antd'

import {
  createUser,
  deleteUser,
  fetchDepartments,
  fetchUserRoles,
  fetchUsers,
  saveUserRoles,
  updateUser,
  type AdminUser,
  type UserPayload,
} from '@/api/admin'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'
import { useTableQuery } from '@/hooks/useTableQuery'
import { PageContainer } from '@/layouts/PageContainer'
import { applyServerFieldErrors } from '@/utils/formErrors'

type UserQuery = { page: number; kw: string }
const DEFAULTS: UserQuery = { page: 1, kw: '' }

export default function Users() {
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<UserPayload>()

  const [params, setParams] = useTableQuery(DEFAULTS)
  const [editing, setEditing] = useState<AdminUser | null | undefined>(undefined)
  const [roleTarget, setRoleTarget] = useState<AdminUser | null>(null)

  const query = useQuery({
    queryKey: ['users', params],
    queryFn: () => fetchUsers(params),
  })
  const depts = useQuery({ queryKey: ['departments'], queryFn: fetchDepartments })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['users'] })

  const save = useMutation({
    mutationFn: (payload: UserPayload) =>
      editing ? updateUser(editing.id, payload) : createUser(payload),
    onSuccess: () => {
      message.success('已保存')
      invalidate()
      setEditing(undefined)
    },
  })

  const remove = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      message.success('已删除')
      invalidate()
    },
    onError: (err: { response?: { data?: { detail?: string } } }) =>
      message.error(err.response?.data?.detail ?? '删除失败：该用户可能有关联数据'),
  })

  const openForm = (user: AdminUser | null) => {
    setEditing(user)
    form.setFieldsValue(
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

  return (
    <PageContainer
      title="用户管理"
      extra={
        <Can perm={PERM.SYSTEM_USER_CREATE}>
          <Button type="primary" onClick={() => openForm(null)}>
            新建用户
          </Button>
        </Can>
      }
    >
      <Input.Search
        placeholder="搜索用户名或姓名"
        allowClear
        defaultValue={params.kw}
        onSearch={(kw) => setParams({ kw, page: 1 })}
        style={{ width: 260, marginBottom: 16 }}
      />

      <Table<AdminUser>
        rowKey="id"
        loading={query.isFetching}
        dataSource={query.data?.results ?? []}
        pagination={{
          current: params.page,
          total: query.data?.count ?? 0,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          showSizeChanger: false,
          onChange: (page) => setParams({ page }),
        }}
        columns={[
          { title: '用户名', dataIndex: 'username', width: 140 },
          { title: '姓名', dataIndex: 'real_name', width: 120 },
          {
            title: '所属部门',
            dataIndex: 'department_name',
            width: 140,
            render: (v: string) => v || '—',
          },
          { title: '手机号', dataIndex: 'phone', width: 130 },
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
                <Can perm={PERM.SYSTEM_USER_UPDATE}>
                  <Button type="link" size="small" onClick={() => openForm(row)}>
                    编辑
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_USER_ASSIGN_ROLE}>
                  <Button type="link" size="small" onClick={() => setRoleTarget(row)}>
                    分配角色
                  </Button>
                </Can>
                <Can perm={PERM.SYSTEM_USER_DELETE}>
                  <Button
                    type="link"
                    size="small"
                    danger
                    onClick={() =>
                      modal.confirm({
                        title: '确认删除？',
                        content: `用户「${row.username}」将被删除。`,
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
        title={editing ? `编辑用户：${editing.username}` : '新建用户'}
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
        {/*
          🔴 这个表单里**没有** is_superuser，也没有密码字段。

             安全红线 4：超管只能通过 createsuperuser 创建。
             表单里出现这个字段的话，任何有 system:user:update 权限的人
             都能把自己变成超管——一次点击完成提权。

             后端的 serializer 白名单也没有它，但前端不该依赖那一点：
             「不要把安全性寄托在对端的实现细节上」。
        */}
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="real_name" label="姓名">
            <Input />
          </Form.Item>
          <Form.Item name="department" label="所属部门">
            <Select
              allowClear
              placeholder="未分配"
              options={(depts.data ?? []).map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <Form.Item name="phone" label="手机号">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <UserRoleModal
        user={roleTarget}
        onClose={() => setRoleTarget(null)}
        onSaved={invalidate}
      />
    </PageContainer>
  )
}

function UserRoleModal({
  user,
  onClose,
  onSaved,
}: {
  user: AdminUser | null
  onClose: () => void
  onSaved: () => void
}) {
  const { message } = App.useApp()
  const [checked, setChecked] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const query = useQuery({
    queryKey: ['user-roles', user?.id],
    queryFn: async () => {
      const data = await fetchUserRoles(user!.id)
      setChecked(data.checked)
      return data
    },
    enabled: user !== null,
  })

  const ungrantable = (query.data?.roles ?? []).filter((r) => !r.grantable)

  return (
    <Modal
      open={user !== null}
      title={`分配角色：${user?.username ?? ''}`}
      onCancel={onClose}
      confirmLoading={saving}
      onOk={async () => {
        if (!user) return
        setSaving(true)
        try {
          const res = await saveUserRoles(user.id, checked)
          if (res.rejected > 0) {
            // ADR-011：不能把自己不具备的角色授予他人。
            // 静默丢弃会让管理员以为分配成功了。
            message.warning(
              `已分配 ${res.saved} 个；忽略了 ${res.rejected} 个超出你自身权限范围的角色`,
            )
          } else {
            message.success(`已分配 ${res.saved} 个角色`)
          }
          onSaved()
          onClose()
        } finally {
          setSaving(false)
        }
      }}
      destroyOnHidden
    >
      {ungrantable.length > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="有些角色你授不出去"
          description="灰色的角色包含你自己不具备的权限。权限不可放大（ADR-011）——否则任何人都能通过「造一个更大的角色再给自己」来提权。"
        />
      )}
      <Checkbox.Group
        value={checked}
        onChange={(v) => setChecked(v as number[])}
        style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        {(query.data?.roles ?? []).map((r) => (
          <Checkbox
            key={r.id}
            value={r.id}
            /*
             * ⚠️ grantable 由后端的 can_grant_role 算，前端不重算。
             *    重算就是把 ADR-011 的规则抄第二遍，两份迟早不一致。
             */
            disabled={!r.grantable}
          >
            {r.name}
            <span style={{ color: '#bfbfbf', marginLeft: 8, fontSize: 12 }}>
              {r.code}
            </span>
          </Checkbox>
        ))}
      </Checkbox.Group>
    </Modal>
  )
}
