import { useEffect } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Button, Card, Descriptions, Space, Typography } from 'antd'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { fetchProfile } from '@/auth/api'
import { useAuthStore } from '@/auth/store'
import { useLogout } from '@/auth/useAuth'
import { RequireAuth } from '@/components/RequireAuth'
import Login from '@/pages/Login'

/**
 * 应用启动时问一次后端「我登录了吗」。
 *
 * 前端不保存 token——它靠这一次请求判断认证状态（F-ADR-002/003）。
 * fe-v0.6.0 会把它换成正式的 useProfileQuery 并接进权限 store。
 */
function useBootstrapAuth() {
  const setProfile = useAuthStore((s) => s.setProfile)
  const reset = useAuthStore((s) => s.reset)

  const query = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
    retry: false,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (query.data) setProfile(query.data)
    else if (query.isError) reset()
  }, [query.data, query.isError, setProfile, reset])
}

/** 把「会话过期怎么办」注入 axios 拦截器——避免 api 层直接依赖路由。 */
function UnauthenticatedBridge() {
  const navigate = useNavigate()
  const reset = useAuthStore((s) => s.reset)

  useEffect(() => {
    setUnauthenticatedHandler(() => {
      reset()
      const here = window.location.pathname + window.location.search
      navigate(`/login?redirect=${encodeURIComponent(here)}`, { replace: true })
    })
  }, [navigate, reset])

  return null
}

/** fe-v0.3.0 的临时首页。真正的后台布局在 fe-v0.4.0。 */
function Home() {
  const user = useAuthStore((s) => s.user)
  const perms = useAuthStore((s) => s.perms)
  const logout = useLogout()

  return (
    <div style={{ maxWidth: 720, margin: '64px auto', padding: 24 }}>
      <Space
        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          已登录
        </Typography.Title>
        <Button onClick={() => logout.mutate()} loading={logout.isPending}>
          退出登录
        </Button>
      </Space>

      <Card title="当前会话">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="用户">
            {user?.realName || user?.username}
          </Descriptions.Item>
          <Descriptions.Item label="部门">
            {user?.department?.name ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="超管">
            {user?.isSuperuser ? '是' : '否'}
          </Descriptions.Item>
          <Descriptions.Item label="权限码数">{perms.length}</Descriptions.Item>
          <Descriptions.Item label="document.cookie">
            <code style={{ fontSize: 12 }}>{document.cookie || '（空）'}</code>
          </Descriptions.Item>
        </Descriptions>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
          ⬆️ 上面这行是 F-ADR-002 的验收：看得到 csrftoken，
          <strong>看不到 sessionid</strong>——真正的凭证是 httpOnly 的。
        </Typography.Paragraph>
      </Card>
    </div>
  )
}

function AppRoutes() {
  useBootstrapAuth()

  return (
    <>
      <UnauthenticatedBridge />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
