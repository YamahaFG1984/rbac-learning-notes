import { useQuery } from '@tanstack/react-query'
import { Alert, Card, Descriptions, Space, Spin, Typography } from 'antd'

import { client } from '@/api/client'

interface HealthPayload {
  detail: string
}

/**
 * fe-v0.1.0：只做一件事——验证同域代理确实打通了。
 *
 * 真正的路由与布局在 fe-v0.3.0 / fe-v0.4.0。
 */
export default function App() {
  const { data, error, isPending } = useQuery({
    queryKey: ['health'],
    queryFn: async () => (await client.get<HealthPayload>('/health/')).data,
    retry: false,
  })

  return (
    <div style={{ maxWidth: 720, margin: '64px auto', padding: 24 }}>
      <Typography.Title level={3}>RBAC 教学系统 · React 前端</Typography.Title>
      <Typography.Paragraph type="secondary">
        fe-v0.1.0：前端骨架与同域代理。两套前端并存——
        <a href="/django/accounts/login/">Django 模板版在这里</a>。
      </Typography.Paragraph>

      <Card title="后端连通性">
        {isPending ? (
          <Space>
            <Spin />
            正在请求 /api/v1/health/
          </Space>
        ) : error ? (
          <Alert
            type="error"
            showIcon
            message="连不上后端"
            description="确认 Django 已在 :8000 运行，且 vite.config.ts 的 proxy 配置正确。"
          />
        ) : (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态">{data?.detail}</Descriptions.Item>
            <Descriptions.Item label="请求地址">
              /api/v1/health/（同域，由 Vite 转发到 :8000）
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>
    </div>
  )
}
