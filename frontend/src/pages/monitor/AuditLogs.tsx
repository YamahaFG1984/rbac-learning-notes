import { useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Descriptions, Input, Modal, Space, Table, Tag } from 'antd'

import { fetchAuditLogs, type AuditLog } from '@/api/admin'
import { useTableQuery } from '@/hooks/useTableQuery'
import { PageContainer } from '@/layouts/PageContainer'

type LogQuery = { page: number; kw: string; action: string }
const DEFAULTS: LogQuery = { page: 1, kw: '', action: '' }

/**
 * 把 detail 里的 added / removed 渲染成一眼能读的东西。
 *
 * ⚠️ 直接 JSON.stringify 出来没人看得懂。
 *
 *    后端 v0.17.0 记录 before/after/added/removed 的理由是
 *    「审计日志要能回答『当时到底发生了什么』」——
 *    展示层不做处理的话，这个价值就打折了。
 *    一条没人读得懂的日志，和没有这条日志的区别不大。
 */
function DetailDiff({ detail }: { detail: Record<string, unknown> }) {
  const added = (detail.added as string[]) ?? []
  const removed = (detail.removed as string[]) ?? []

  if (added.length === 0 && removed.length === 0) return null

  return (
    <Space size={[0, 4]} wrap>
      {added.map((code) => (
        <Tag key={`+${code}`} color="green">
          + {code}
        </Tag>
      ))}
      {removed.map((code) => (
        <Tag key={`-${code}`} color="red">
          − {code}
        </Tag>
      ))}
    </Space>
  )
}

export default function AuditLogs() {
  const [params, setParams] = useTableQuery(DEFAULTS)
  const [detail, setDetail] = useState<AuditLog | null>(null)

  const query = useQuery({
    queryKey: ['audit-logs', params],
    queryFn: () => fetchAuditLogs(params),
  })

  return (
    <PageContainer title="审计日志">
      <Input.Search
        placeholder="搜索操作者或目标"
        allowClear
        defaultValue={params.kw}
        onSearch={(kw) => setParams({ kw, page: 1 })}
        style={{ width: 260, marginBottom: 16 }}
      />

      <Table<AuditLog>
        rowKey="id"
        loading={query.isFetching}
        dataSource={query.data?.results ?? []}
        onRow={(row) => ({ onClick: () => setDetail(row) })}
        pagination={{
          current: params.page,
          total: query.data?.count ?? 0,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          showSizeChanger: false,
          onChange: (page) => setParams({ page }),
        }}
        columns={[
          {
            title: '时间',
            dataIndex: 'created_at',
            width: 170,
            render: (v: string) => v.replace('T', ' ').slice(0, 19),
          },
          {
            title: '操作者',
            dataIndex: 'actor_name',
            width: 120,
            /* 冗余快照：用户被删除后 actor 变 null，但这里还留着当时是谁 */
            render: (v: string) => v || '（已删除）',
          },
          { title: '动作', dataIndex: 'action_display', width: 130 },
          {
            title: '目标',
            dataIndex: 'target_repr',
            width: 160,
            render: (v: string) => v || '—',
          },
          {
            title: '变更',
            key: 'diff',
            render: (_, row) => <DetailDiff detail={row.detail} />,
          },
          {
            title: '结果',
            dataIndex: 'result',
            width: 80,
            render: (v: string, row) =>
              v === 'success' ? (
                <Tag color="green">{row.result_display}</Tag>
              ) : (
                <Tag color="red">{row.result_display}</Tag>
              ),
          },
          { title: 'IP', dataIndex: 'ip', width: 130 },
        ]}
      />

      <Modal
        open={detail !== null}
        title="审计详情"
        footer={null}
        width={720}
        onCancel={() => setDetail(null)}
      >
        {detail && (
          <>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="时间">
                {detail.created_at.replace('T', ' ').slice(0, 19)}
              </Descriptions.Item>
              <Descriptions.Item label="操作者">
                {detail.actor_name || '（已删除）'}
              </Descriptions.Item>
              <Descriptions.Item label="动作">{detail.action_display}</Descriptions.Item>
              <Descriptions.Item label="目标">
                {detail.target_repr || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="IP">{detail.ip ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="结果">{detail.result_display}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 16 }}>
              <DetailDiff detail={detail.detail} />
            </div>

            {/* 结构化展示之外仍保留原始 JSON —— 展示层的解读可能有遗漏，
                原始记录才是审计的依据 */}
            <pre
              style={{
                marginTop: 12,
                padding: 12,
                background: 'rgba(0,0,0,0.04)',
                borderRadius: 4,
                fontSize: 12,
                maxHeight: 280,
                overflow: 'auto',
              }}
            >
              {JSON.stringify(detail.detail, null, 2)}
            </pre>
          </>
        )}
      </Modal>
    </PageContainer>
  )
}
