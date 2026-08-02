import { useEffect } from 'react'

import { Form, Modal, Select } from 'antd'

import { applyServerFieldErrors } from '@/utils/formErrors'

import { useAssignableUsers } from './useTicketMutations'

interface Props {
  open: boolean
  currentAssignee: number | null
  confirmLoading?: boolean
  onCancel: () => void
  onSubmit: (assignee: number | null) => Promise<unknown>
}

/**
 * 派单。
 *
 * ⚠️ 候选人列表来自 /tickets/assignable-users/，权限点是 ticket:ticket:assign。
 *    它**没有**复用 /api/v1/users/ —— 那个接口要 system:user:view，
 *    而 cs_manager 只有派单权限。
 *
 *    如果图省事复用了，结果就是「为了让主管能派单，只好给他用户管理权限」。
 *    权限点被业务需求倒逼着变粗，是权限模型腐化的典型路径。
 */
export function AssignModal({
  open,
  currentAssignee,
  confirmLoading,
  onCancel,
  onSubmit,
}: Props) {
  const [form] = Form.useForm<{ assignee: number | null }>()
  const assignees = useAssignableUsers(open)

  useEffect(() => {
    if (open) form.setFieldsValue({ assignee: currentAssignee })
  }, [open, currentAssignee, form])

  const handleOk = async () => {
    const { assignee } = await form.validateFields()
    try {
      await onSubmit(assignee ?? null)
      onCancel()
    } catch (err) {
      // 后端说了算 —— 前端不复制业务规则，只把错误显示出来
      applyServerFieldErrors(form, err)
    }
  }

  return (
    <Modal
      open={open}
      title="派单"
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={confirmLoading}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="assignee" label="处理人">
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
