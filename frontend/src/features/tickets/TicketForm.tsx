import { Form, Input, Modal, Select } from 'antd'
import { useEffect } from 'react'

import type { Ticket, TicketPayload } from '@/api/tickets'
import { applyServerFieldErrors } from '@/utils/formErrors'

import { useAssignableUsers } from './useTicketMutations'

interface Props {
  open: boolean
  /** 有值 = 编辑，无值 = 新建 */
  ticket?: Ticket
  confirmLoading?: boolean
  onCancel: () => void
  onSubmit: (payload: TicketPayload) => Promise<unknown>
}

/**
 * 新建 / 编辑工单。
 *
 * ⚠️ 表单里**没有** creator 和 department 字段。
 *
 *    后端的 TicketSerializer 把它们设成了 read_only，提交了也会被忽略——
 *    但前端不该依赖这一点。理由是**不要把安全性寄托在对端的实现细节上**：
 *    后端某天改了 serializer，前端的伪造就会立刻生效。
 *
 *    这和模板版 TicketForm 用白名单 fields 而不是 exclude 是同一条原则。
 */
export function TicketForm({
  open,
  ticket,
  confirmLoading,
  onCancel,
  onSubmit,
}: Props) {
  const [form] = Form.useForm<TicketPayload>()
  // 关着的时候不请求候选人 —— 打开表单才是需要它的时刻
  const assignees = useAssignableUsers(open)

  useEffect(() => {
    if (!open) return
    form.setFieldsValue(
      ticket
        ? {
            title: ticket.title,
            content: ticket.content,
            priority: ticket.priority,
            status: ticket.status,
            assignee: ticket.assignee,
          }
        : { title: '', content: '', priority: 2, status: 'open', assignee: null },
    )
  }, [open, ticket, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    try {
      await onSubmit(values)
      onCancel()
    } catch (err) {
      // 后端说了算 —— 前端不复制业务规则，只把错误显示出来
      applyServerFieldErrors(form, err)
    }
  }

  return (
    <Modal
      open={open}
      title={ticket ? `编辑工单：${ticket.title}` : '新建工单'}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={confirmLoading}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="title"
          label="标题"
          rules={[{ required: true, message: '请输入标题' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="content" label="内容">
          <Input.TextArea rows={4} />
        </Form.Item>
        <Form.Item name="priority" label="优先级">
          <Select
            options={[
              { value: 1, label: '低' },
              { value: 2, label: '中' },
              { value: 3, label: '高' },
            ]}
          />
        </Form.Item>
        <Form.Item name="status" label="状态">
          <Select
            options={[
              { value: 'open', label: '待处理' },
              { value: 'processing', label: '处理中' },
              { value: 'closed', label: '已关闭' },
            ]}
          />
        </Form.Item>
        <Form.Item name="assignee" label="处理人">
          {/*
            ⚠️ 候选人来自 /tickets/assignable-users/，只含**你数据范围内**的人。
               不是「全部用户」——那样一个没有 system:user:view 的人
               就通过这个下拉框看到了公司完整的用户名册。
               后端 v0.15.0 的模板表单曾经就是这么写的。
          */}
          <Select
            allowClear
            loading={assignees.isLoading}
            placeholder="未指派"
            options={assignees.data?.map((u) => ({
              value: u.id,
              label: `${u.real_name || u.username}（${u.department_name}）`,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
