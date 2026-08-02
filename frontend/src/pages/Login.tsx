import { useEffect } from 'react'

import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useNavigate, useSearchParams } from 'react-router'

import { useLogin } from '@/auth/useAuth'
import { useAuthStore } from '@/auth/store'

/**
 * 校验 redirect 参数，只接受站内路径。
 *
 * `//evil.com` 会被浏览器当成协议相对 URL 跳到外站——
 * 这是后端 v0.7.0 用 url_has_allowed_host_and_scheme 防的
 * **同一个开放重定向问题的前端版本**。
 */
function safeRedirect(raw: string | null): string {
  if (!raw) return '/'
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/'
  return raw
}

export default function Login() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const status = useAuthStore((s) => s.status)
  const login = useLogin()

  const target = safeRedirect(searchParams.get('redirect'))

  useEffect(() => {
    if (status === 'authenticated') navigate(target, { replace: true })
  }, [status, target, navigate])

  // ⚠️ 登录失败是 400 不是 401（后端 fe-v0.2.0 刻意如此）。
  //    400 不会触发 client.ts 里的「跳登录页」——用户留在本页看错误提示。
  const detail =
    (login.error as { response?: { data?: { detail?: string } } } | null)
      ?.response?.data?.detail ?? null

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <Card style={{ width: 380 }}>
        <Typography.Title level={4} style={{ textAlign: 'center' }}>
          RBAC 教学系统
        </Typography.Title>

        {detail && (
          <Alert type="error" showIcon message={detail} style={{ marginBottom: 16 }} />
        )}

        <Form
          layout="vertical"
          onFinish={(values: { username: string; password: string }) =>
            login.mutate(values)
          }
          autoComplete="off"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input autoFocus size="large" />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password size="large" />
          </Form.Item>

          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={login.isPending}
          >
            登录
          </Button>
        </Form>

        <Typography.Paragraph
          type="secondary"
          style={{ marginTop: 16, marginBottom: 0, fontSize: 12 }}
        >
          演示账号：superadmin / sysadmin / cs_manager / cs_staff / no_role，
          统一密码 demo1234。
          <br />
          <a href="/django/accounts/login/">Django 模板版在这里</a>
        </Typography.Paragraph>
      </Card>
    </div>
  )
}
