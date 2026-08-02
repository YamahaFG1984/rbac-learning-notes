import { Layout } from 'antd'
import { Outlet } from 'react-router'

import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function AdminLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar />
      <Layout>
        <Topbar />
        <Layout.Content style={{ padding: 24 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
