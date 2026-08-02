import { useMemo, useState } from 'react'

import { App, Button, Space, Table, Tag, type TableColumnsType } from 'antd'
import { Link } from 'react-router'

import {
  exportTicketsUrl,
  type Ticket,
  type TicketPriority,
  type TicketStatus,
} from '@/api/tickets'
import { usePermission } from '@/auth/usePermission'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'
import { AssignModal } from '@/features/tickets/AssignModal'
import { TicketFilters } from '@/features/tickets/TicketFilters'
import { TicketForm } from '@/features/tickets/TicketForm'
import { useTicketList } from '@/features/tickets/useTicketList'
import { useTicketMutations } from '@/features/tickets/useTicketMutations'
import { useTableQuery } from '@/hooks/useTableQuery'
import { PageContainer } from '@/layouts/PageContainer'

/**
 * ⚠️ 必须是 `type` 不能是 `interface`。
 *
 *    useTableQuery 的约束是 `T extends Record<string, string | number>`，
 *    而 TypeScript 只给**类型别名**隐式索引签名，不给 interface。
 *    写成 interface 的话报错是
 *    「'TicketQuery' is not assignable to 'Record<string, string | number>'」
 *    ——看起来像字段类型不对，其实和字段毫无关系。
 */
type TicketQuery = {
  page: number
  kw: string
  status: TicketStatus | ''
  priority: TicketPriority | ''
}

/**
 * 模块级常量：引用稳定，useTableQuery 的 useMemo 才不会每次重算。
 *
 * ⚠️ 这些值来自 URL，用户可以随便改成 `?status=xyz`。
 *    类型标注在这里是**一厢情愿**的——TS 管不到运行时的 URL。
 *
 *    这没关系：后端拿到无效值只会筛出 0 条，**不可能筛出更多**。
 *    （tests/api/test_api_permissions.py::test_filter_cannot_widen_scope
 *      就是在钉这一点：任何筛选参数都只能收窄，不能放宽。）
 *    前端不必为此做校验——校验放在这里又是一层会漂移的重复逻辑。
 */
const DEFAULTS: TicketQuery = { page: 1, kw: '', status: '', priority: '' }

const PRIORITY_TAG: Record<number, { color: string; text: string }> = {
  1: { color: 'default', text: '低' },
  2: { color: 'blue', text: '中' },
  3: { color: 'red', text: '高' },
}

export default function TicketList() {
  const [params, setParams] = useTableQuery(DEFAULTS)
  const query = useTicketList(params)
  const { create, remove, assign } = useTicketMutations()
  const { modal } = App.useApp()

  const [creating, setCreating] = useState(false)
  const [assigningId, setAssigningId] = useState<number | null>(null)

  /*
   * ⚠️ 删除必须二次确认。
   *
   *    这不只是体验问题：列表页的删除按钮和行是对齐的，
   *    误点一行删掉另一行的数据是真实会发生的事。
   *    确认框里带上标题，让用户确认的是「这一条」而不是「删除」这个动作。
   */
  const confirmRemove = (row: Ticket) =>
    modal.confirm({
      title: '确认删除？',
      content: `工单「${row.title}」将被删除，此操作不可撤销。`,
      okType: 'danger',
      onOk: () => remove.mutateAsync(row.id),
    })

  /*
   * ⚠️ hook 不能在 columns 数组里条件调用。
   *    在组件顶层拿到 can，让 columns 闭包捕获它。
   */
  const can = usePermission()

  const columns: TableColumnsType<Ticket> = useMemo(
    () => [
      {
        title: '标题',
        dataIndex: 'title',
        render: (title: string, row) => <Link to={`/tickets/${row.id}`}>{title}</Link>,
      },
      { title: '状态', dataIndex: 'status_display', width: 100 },
      {
        title: '优先级',
        dataIndex: 'priority',
        width: 90,
        render: (p: number) => (
          <Tag color={PRIORITY_TAG[p]?.color}>{PRIORITY_TAG[p]?.text ?? p}</Tag>
        ),
      },
      { title: '创建人', dataIndex: 'creator_name', width: 110 },
      { title: '归属部门', dataIndex: 'department_name', width: 120 },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        width: 170,
        render: (v: string) => v.replace('T', ' ').slice(0, 16),
      },
      /*
       * ⚠️ 一个操作都没有的用户，不该看到一列空白的「操作」。
       *
       *    列的增减是**数据**层面的判断，只能用 hook 式；
       *    列内每个按钮才用组件式 <Can>。两种接口各司其职。
       */
      ...(can(PERM.TICKET_TICKET_UPDATE) ||
      can(PERM.TICKET_TICKET_DELETE) ||
      can(PERM.TICKET_TICKET_ASSIGN)
        ? [
            {
              title: '操作',
              key: 'action',
              width: 160,
              render: (_: unknown, row: Ticket) => (
                <Space size={4}>
                  <Can perm={PERM.TICKET_TICKET_UPDATE}>
                    <Link to={`/tickets/${row.id}`}>编辑</Link>
                  </Can>
                  {/*
                    ⚠️ fe-v0.9.0 我把「派单」放在了页面工具栏里 —— 那是错的。
                       派单是针对**某一条**工单的操作（后端路由是
                       /tickets/<pk>/assign/），放工具栏等于问「派哪一单」。
                       权限点画得对，界面位置画错了：
                       **权限点的粒度是「界面上一个可点的东西」，
                       那就得先把这个东西放对地方。**
                  */}
                  <Can perm={PERM.TICKET_TICKET_ASSIGN}>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => setAssigningId(row.id)}
                    >
                      派单
                    </Button>
                  </Can>
                  <Can perm={PERM.TICKET_TICKET_DELETE}>
                    <Button
                      type="link"
                      size="small"
                      danger
                      onClick={() => confirmRemove(row)}
                    >
                      删除
                    </Button>
                  </Can>
                </Space>
              ),
            },
          ]
        : []),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [can],
  )

  return (
    <PageContainer
      title="工单列表"
      extra={
        <>
          <Can perm={PERM.TICKET_TICKET_CREATE}>
            <Button type="primary" onClick={() => setCreating(true)}>
              新建工单
            </Button>
          </Can>
          <Can perm={PERM.TICKET_TICKET_EXPORT}>
            <Button
              /*
               * 导出走后端同一条 .for_user() 链路。
               * 前端自己拼 CSV 的话导出的是「当前页」，而且绕过了 EXPORT 权限。
               */
              onClick={() => window.open(exportTicketsUrl(params))}
            >
              导出
            </Button>
          </Can>
        </>
      }
    >
      <TicketFilters params={params} onChange={setParams} />

      <Table<Ticket>
        rowKey="id"
        columns={columns}
        dataSource={query.data?.results ?? []}
        loading={query.isFetching}
        pagination={{
          current: params.page,
          /*
           * ⚠️ total 直接用后端的 count，**不重新计算**。
           *
           *    前端如果对 results 再过滤一次，这里就会出现
           *    「显示 40 条，分页器说 50 条」的经典错位——
           *    而且那次过滤零安全价值：数据早就到浏览器了（F-ADR-015）。
           */
          total: query.data?.count ?? 0,
          pageSize: 20,
          showTotal: (total) => `共 ${total} 条`,
          showSizeChanger: false,
          onChange: (page) => setParams({ page }),
        }}
      />

      <TicketForm
        open={creating}
        confirmLoading={create.isPending}
        onCancel={() => setCreating(false)}
        onSubmit={(payload) => create.mutateAsync(payload)}
      />
      <AssignModal
        open={assigningId !== null}
        currentAssignee={
          query.data?.results.find((t) => t.id === assigningId)?.assignee ?? null
        }
        confirmLoading={assign.isPending}
        onCancel={() => setAssigningId(null)}
        onSubmit={(assignee) =>
          assign.mutateAsync({ targetId: assigningId!, assignee })
        }
      />
    </PageContainer>
  )
}
