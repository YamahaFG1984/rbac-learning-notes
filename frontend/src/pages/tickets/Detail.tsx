import { useState } from 'react'

import { Button, Descriptions, Skeleton, Tag } from 'antd'
import type { AxiosError } from 'axios'
import { useNavigate, useParams } from 'react-router'

import type { TicketPayload } from '@/api/tickets'
import { Can } from '@/components/Can'
import { ErrorResult } from '@/components/ErrorResult'
import { ResourceNotFound } from '@/components/ResourceNotFound'
import { PERM } from '@/constants/permissions'
import { AssignModal } from '@/features/tickets/AssignModal'
import { TicketForm } from '@/features/tickets/TicketForm'
import {
  useTicketMutations,
  useTicketQuery,
} from '@/features/tickets/useTicketMutations'
import { PageContainer } from '@/layouts/PageContainer'

const PRIORITY: Record<number, string> = { 1: '低', 2: '中', 3: '高' }

export default function TicketDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const ticketId = Number(id)

  const { data, error, isLoading } = useTicketQuery(ticketId)
  const { update, remove, assign } = useTicketMutations(ticketId)

  const [editing, setEditing] = useState(false)
  const [assigning, setAssigning] = useState(false)

  if (isLoading) return <Skeleton active />

  /*
   * 🔴 404 必须**整页替换**，不能只弹个 toast。
   *
   *    弹 toast 的话用户停在一个空白页上，不知道该干什么；
   *    而且 toast 三秒后消失，刷新一次就再也看不到原因了。
   *
   *    全局拦截器负责通用处理（fe-v0.14.0），
   *    「详情页拿不到数据」这种是页面级的事，页面自己管。
   */
  const status = (error as AxiosError | null)?.response?.status
  if (status === 404) return <ResourceNotFound />
  if (error || !data) return <ErrorResult />

  const handleUpdate = (payload: TicketPayload) => update.mutateAsync(payload)

  return (
    <PageContainer
      title={data.title}
      extra={
        <>
          <Can perm={PERM.TICKET_TICKET_UPDATE}>
            <Button onClick={() => setEditing(true)}>编辑</Button>
          </Can>
          <Can perm={PERM.TICKET_TICKET_ASSIGN}>
            <Button onClick={() => setAssigning(true)}>派单</Button>
          </Can>
          <Can perm={PERM.TICKET_TICKET_DELETE}>
            <Button
              danger
              loading={remove.isPending}
              onClick={async () => {
                await remove.mutateAsync(ticketId)
                navigate('/tickets')
              }}
            >
              删除
            </Button>
          </Can>
        </>
      }
    >
      <Descriptions bordered column={2} size="middle">
        <Descriptions.Item label="状态">{data.status_display}</Descriptions.Item>
        <Descriptions.Item label="优先级">
          <Tag>{PRIORITY[data.priority] ?? data.priority}</Tag>
        </Descriptions.Item>
        {/*
          creator / department 只读展示 —— 它们由后端从 request.user 快照，
          界面上没有任何地方能改它们（同模板版的白名单 fields）。
        */}
        <Descriptions.Item label="创建人">{data.creator_name}</Descriptions.Item>
        <Descriptions.Item label="归属部门">
          {data.department_name}
        </Descriptions.Item>
        <Descriptions.Item label="创建时间">
          {data.created_at.replace('T', ' ').slice(0, 16)}
        </Descriptions.Item>
        <Descriptions.Item label="更新时间">
          {data.updated_at.replace('T', ' ').slice(0, 16)}
        </Descriptions.Item>
        <Descriptions.Item label="内容" span={2}>
          <div style={{ whiteSpace: 'pre-wrap' }}>{data.content || '（无）'}</div>
        </Descriptions.Item>
      </Descriptions>

      <TicketForm
        open={editing}
        ticket={data}
        confirmLoading={update.isPending}
        onCancel={() => setEditing(false)}
        onSubmit={handleUpdate}
      />
      <AssignModal
        open={assigning}
        currentAssignee={data.assignee}
        confirmLoading={assign.isPending}
        onCancel={() => setAssigning(false)}
        onSubmit={(assignee) => assign.mutateAsync({ targetId: ticketId, assignee })}
      />
    </PageContainer>
  )
}
