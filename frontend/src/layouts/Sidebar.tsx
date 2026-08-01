import {
  AppstoreOutlined,
  BarChartOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Layout, Menu, type MenuProps } from 'antd'
import { useLocation, useNavigate } from 'react-router'

import { useUiStore } from '@/store/uiStore'

/**
 * ⚠️ fe-v0.4.0：菜单**硬编码**，没有任何权限判断。
 *
 *    fe-v0.8.0 会改为由 profile 的 menus 渲染。保持结构简单，
 *    让那次改动的 diff 只讲「动态化」这一件事——
 *    和后端 v0.8.0 → v0.11.0 是同一个手法。
 *
 *    在此之前，所有登录用户都能看到全部菜单，包括他点进去会 403 的。
 *    这个难看的状态是刻意的：它让你直观感受到为什么要做动态菜单。
 */
const STATIC_ITEMS: MenuProps['items'] = [
  {
    key: 'ticket',
    icon: <FileTextOutlined />,
    label: '工单管理',
    children: [{ key: '/tickets', label: '工单列表' }],
  },
  {
    key: 'system',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/system/depts', label: '部门管理' },
      { key: '/system/users', label: '用户管理' },
      { key: '/system/roles', label: '角色管理' },
      { key: '/system/perms', label: '权限点' },
    ],
  },
  {
    key: 'monitor',
    icon: <BarChartOutlined />,
    label: '系统监控',
    children: [{ key: '/monitor/audit', label: '审计日志' }],
  },
]

export function Sidebar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const collapsed = useUiStore((s) => s.siderCollapsed)

  return (
    <Layout.Sider collapsed={collapsed} theme="dark" width={220}>
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 600,
          letterSpacing: 1,
        }}
      >
        {collapsed ? <AppstoreOutlined /> : 'RBAC 教学系统'}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[pathname]}
        defaultOpenKeys={['ticket', 'system', 'monitor']}
        items={STATIC_ITEMS}
        onClick={({ key }) => navigate(key)}
      />
    </Layout.Sider>
  )
}
