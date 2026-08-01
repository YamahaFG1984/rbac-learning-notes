import { Button, Space, Table, type TableColumnsType } from 'antd'

import { usePermission } from '@/auth/usePermission'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'
import { PageContainer } from '@/layouts/PageContainer'

interface Row {
  id: number
  title: string
  status: string
}

/** 真实数据在 fe-v0.10.0 接。本 tag 只关心「按钮该不该出现」。 */
const ROWS: Row[] = [
  { id: 1, title: '（fe-v0.10.0 接真实数据）', status: '待处理' },
]

export default function TicketList() {
  /*
   * hook 式：用于**数据**。
   *
   * AntD 的 columns / items / disabled 都是数据不是 JSX，包不进 <Can>。
   * 所以两个接口都要——但它们内部是同一个判断函数（usePermission）。
   */
  const can = usePermission()

  const columns: TableColumnsType<Row> = [
    { title: '标题', dataIndex: 'title' },
    { title: '状态', dataIndex: 'status' },
    // 一个操作都没有的用户，不该看到一列空白的「操作」
    ...(can(PERM.TICKET_TICKET_UPDATE) || can(PERM.TICKET_TICKET_DELETE)
      ? [
          {
            title: '操作',
            key: 'action',
            render: () => (
              <Space>
                {/* 组件式：用于**渲染** */}
                <Can perm={PERM.TICKET_TICKET_UPDATE}>
                  <Button type="link" size="small">
                    编辑
                  </Button>
                </Can>
                <Can perm={PERM.TICKET_TICKET_DELETE}>
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Can>
              </Space>
            ),
          },
        ]
      : []),
  ]

  return (
    <PageContainer
      title="工单列表"
      extra={
        <>
          <Can perm={PERM.TICKET_TICKET_CREATE}>
            <Button type="primary">新建工单</Button>
          </Can>
          <Can perm={PERM.TICKET_TICKET_ASSIGN}>
            <Button>派单</Button>
          </Can>
          <Can perm={PERM.TICKET_TICKET_EXPORT}>
            <Button>导出</Button>
          </Can>
        </>
      }
    >
      <Table<Row>
        rowKey="id"
        columns={columns}
        dataSource={ROWS}
        pagination={false}
      />
    </PageContainer>
  )
}
