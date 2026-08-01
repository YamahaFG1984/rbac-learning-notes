import { useEffect } from 'react'

import { useQuery } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { fetchProfile } from '@/auth/api'
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

/**
 * 应用启动时问一次后端「我登录了吗」。
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

/**
 * ⚠️ fe-v0.4.0：**静态路由表**，没有任何权限判断。
 *
 *    所有登录用户都能进所有页面——包括他没权限的（进去后接口会 403）。
 *    fe-v0.7.0 会改为由 profile 的 menus 动态注册 + PermissionGate 守卫。
 *
 *    这个难看的中间态是刻意的，理由同 Sidebar.tsx 的注释。
 */
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
