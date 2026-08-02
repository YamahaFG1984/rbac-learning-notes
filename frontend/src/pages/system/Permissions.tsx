import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Alert, Table, Tag } from 'antd'

import { fetchPermissions, type Permission } from '@/api/admin'
import { PageContainer } from '@/layouts/PageContainer'

interface Row extends Permission {
  children?: Row[]
}

const TYPE_TAG: Record<string, { color: string; text: string }> = {
  catalog: { color: 'default', text: '目录' },
  menu: { color: 'blue', text: '菜单' },
  button: { color: 'green', text: '按钮' },
}

export default function Permissions() {
  const query = useQuery({ queryKey: ['permissions'], queryFn: fetchPermissions })

  const tree = useMemo<Row[]>(() => {
    const rows = query.data ?? []
    const byParent = new Map<number | null, Permission[]>()
    for (const p of rows) {
      const list = byParent.get(p.parent) ?? []
      list.push(p)
      byParent.set(p.parent, list)
    }
    const build = (parent: number | null): Row[] =>
      (byParent.get(parent) ?? []).map((p) => {
        const children = build(p.id)
        return children.length > 0 ? { ...p, children } : { ...p }
      })
    return build(null)
  }, [query.data])

  return (
    <PageContainer title="权限点">
      {/*
        ⚠️ 这个页面**只读**，没有任何编辑按钮。

           权限点由 apps/<app>/permissions.py 声明，经 sync_permissions 入库（ADR-004）。
           开一个「新增权限点」的界面，就等于允许运行时凭空造出一个
           代码里没有人检查的权限码——它永远不会生效，却会出现在角色配置里，
           让管理员以为自己授予了什么。

           权限点的真相在代码里，不在数据库里。
      */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="权限点由代码声明，此页只读"
        description="新增或修改权限点请改 apps/<app>/permissions.py，再运行 python manage.py sync_permissions。数据库不是权限点的真相来源。"
      />

      <Table<Row>
        rowKey="id"
        loading={query.isFetching}
        dataSource={tree}
        pagination={false}
        defaultExpandAllRows
        columns={[
          { title: '名称', dataIndex: 'name' },
          {
            title: '权限码',
            dataIndex: 'code',
            width: 260,
            /* catalog 没有权限码，它只是分组容器 */
            render: (v: string | null) =>
              v ? <code>{v}</code> : <span style={{ color: '#bfbfbf' }}>—</span>,
          },
          {
            title: '类型',
            dataIndex: 'perm_type',
            width: 90,
            render: (v: string) => (
              <Tag color={TYPE_TAG[v]?.color}>{TYPE_TAG[v]?.text ?? v}</Tag>
            ),
          },
          {
            title: '状态',
            key: 'status',
            width: 110,
            render: (_, row) =>
              row.is_deprecated ? (
                /* 废弃而不是删除：删掉的话，历史授权记录会变成孤儿 */
                <Tag color="orange">已废弃</Tag>
              ) : row.is_active ? (
                <Tag color="green">启用</Tag>
              ) : (
                <Tag>停用</Tag>
              ),
          },
        ]}
      />
    </PageContainer>
  )
}
