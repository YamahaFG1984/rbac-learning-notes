import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { Button, Layout, Space, Tag, Typography } from 'antd'

import { useAuthStore } from '@/auth/store'
import { useLogout } from '@/auth/useAuth'
import { useUiStore } from '@/store/uiStore'

export function Topbar() {
  const user = useAuthStore((s) => s.user)
  const { siderCollapsed, toggleSider } = useUiStore()
  const logout = useLogout()

  return (
    <Layout.Header
      style={{
        background: '#fff',
        padding: '0 16px 0 0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 56,
        lineHeight: '56px',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      <Button
        type="text"
        icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        onClick={toggleSider}
      />
      <Space>
        <Typography.Text type="secondary">
          {user?.department?.name ? `${user.department.name} · ` : ''}
          {user?.realName || user?.username}
        </Typography.Text>
        {user?.isSuperuser && <Tag color="gold">超管</Tag>}
        <Button size="small" onClick={() => logout.mutate()} loading={logout.isPending}>
          退出登录
        </Button>
      </Space>
    </Layout.Header>
  )
}
