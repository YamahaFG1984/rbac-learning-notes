import { useEffect } from 'react'

import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { AuthBootstrap } from '@/auth/AuthBootstrap'
import { useAuthStore } from '@/auth/store'
import { RequireAuth } from '@/components/RequireAuth'
import { AdminLayout } from '@/layouts/AdminLayout'
import Forbidden from '@/pages/Forbidden'
import Login from '@/pages/Login'
import NotFound from '@/pages/NotFound'
import AuditLogs from '@/pages/monitor/AuditLogs'
import Departments from '@/pages/system/Departments'
import Permissions from '@/pages/system/Permissions'
import Roles from '@/pages/system/Roles'
import Users from '@/pages/system/Users'
import TicketDetail from '@/pages/tickets/Detail'
import TicketList from '@/pages/tickets/List'

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

/**
 * ⚠️ fe-v0.6.0：路由表仍然是**静态**的，没有权限守卫。
 *    fe-v0.7.0 会改为由 profile 的 menus 动态注册 + PermissionGate。
 *
 * 层次很重要（见 AuthBootstrap 的注释）：
 *
 *     AuthBootstrap        ← 触发 profile 请求，确定认证状态
 *       └── Routes
 *             ├── /login          （公开）
 *             └── RequireAuth     ← 依赖认证状态
 *                   └── AdminLayout
 *
 * AuthBootstrap 必须在 RequireAuth **外面**，否则死锁——
 * 谁负责确定状态，就得在依赖这个状态的东西之上。
 * fe-v0.7.0 的动态路由注册会进一步依赖这个层次。
 */
function AppRoutes() {
  return (
    <AuthBootstrap>
      <UnauthenticatedBridge />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <AdminLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/tickets" replace />} />
          <Route path="tickets" element={<TicketList />} />
          <Route path="tickets/:id" element={<TicketDetail />} />
          <Route path="system/depts" element={<Departments />} />
          <Route path="system/users" element={<Users />} />
          <Route path="system/roles" element={<Roles />} />
          <Route path="system/perms" element={<Permissions />} />
          <Route path="monitor/audit" element={<AuditLogs />} />
          <Route path="403" element={<Forbidden />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </AuthBootstrap>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
