import { Input, Select, Space } from 'antd'

import type { TicketListParams } from '@/api/tickets'

interface Props {
  params: TicketListParams
  onChange: (patch: Partial<TicketListParams>) => void
}

/**
 * ⚠️ 每次改筛选条件都要把 page 重置回 1。
 *
 *    不重置的话：用户在第 4 页筛一个只有 3 条结果的条件，
 *    页面显示「暂无数据」——因为第 4 页确实是空的。
 *    用户会以为筛选坏了。
 */
export function TicketFilters({ params, onChange }: Props) {
  const patch = (p: Partial<TicketListParams>) => onChange({ ...p, page: 1 })

  return (
    <Space style={{ marginBottom: 16 }} wrap>
      <Input.Search
        placeholder="搜索标题或内容"
        allowClear
        defaultValue={params.kw}
        onSearch={(value) => patch({ kw: value })}
        style={{ width: 240 }}
      />
      <Select
        placeholder="状态"
        allowClear
        value={params.status || undefined}
        onChange={(value) => patch({ status: value ?? '' })}
        style={{ width: 120 }}
        options={[
          { value: 'open', label: '待处理' },
          { value: 'processing', label: '处理中' },
          { value: 'closed', label: '已关闭' },
        ]}
      />
      <Select
        placeholder="优先级"
        allowClear
        value={params.priority || undefined}
        onChange={(value) => patch({ priority: value ?? '' })}
        style={{ width: 120 }}
        options={[
          { value: 1, label: '低' },
          { value: 2, label: '中' },
          { value: 3, label: '高' },
        ]}
      />
    </Space>
  )
}
