import { useMemo } from 'react'

import { Navigate, Route, Routes, useLocation, matchPath } from 'react-router'

import { useAuthStore } from '@/auth/store'
import { RequireAuth } from '@/components/RequireAuth'
import { AdminLayout } from '@/layouts/AdminLayout'
import Forbidden from '@/pages/Forbidden'
import Login from '@/pages/Login'
import NotFound from '@/pages/NotFound'

import { buildRoutes } from './buildRoutes'
import { STATIC_ROUTES } from './staticRoutes'

/**
 * 兜底路由：区分「路径存在但你没权限」和「路径根本不存在」。
 *
 * ⚠️ 动态注册的副作用是**两者都匹配不到路由**，默认都会掉进这里。
 *    如果一律返回 404，用户会以为「链接失效了」而不是「我没权限」，
 *    然后去问 IT 为什么链接坏了。
 *
 *    knownRoutes 是后端下发的**全部**菜单路径（含无权限的），
 *    用它来判断该给 403 还是 404。
 */
function UnknownPath() {
  const location = useLocation()
  const knownRoutes = useAuthStore((s) => s.knownRoutes)

  const isKnown = knownRoutes.some(
    (route) =>
      matchPath({ path: route, end: false }, location.pathname) !== null,
  )

  return isKnown ? <Forbidden /> : <NotFound />
}

/**
 * 动态路由。
 *
 * ⚠️ 时序是本 tag 最容易出 bug 的地方，靠两件事保证：
 *
 *   1. AppRouter 在 AuthBootstrap 内部 —— 渲染到这里时 menus 一定有值。
 *      否则「在 /tickets/42 按 F5」会因为路由表是空的而掉进 404。
 *
 *   2. useMemo 用**内容指纹**做依赖，不用 menus 数组本身。
 *      Zustand 的 selector 返回数组时引用可能变，直接依赖会导致
 *      路由表每次渲染都重建——表现是「输入框每敲一个字就失焦」。
 */
export function AppRouter() {
  const menus = useAuthStore((s) => s.menus)

  const fingerprint = useMemo(() => {
    const parts: string[] = []
    const walk = (nodes: typeof menus) => {
      for (const n of nodes) {
        parts.push(`${n.id}:${n.routePath ?? ''}:${n.component ?? ''}`)
        walk(n.children)
      }
    }
    walk(menus)
    return parts.join('|')
  }, [menus])

  const dynamicRoutes = useMemo(
    () => buildRoutes(menus),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fingerprint],
  )

  return (
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
        <Route index element={<HomeRedirect />} />
        {dynamicRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={route.element} />
        ))}
        {/* 详情/编辑这类不在菜单里的页面，靠静态表 + 守卫（F-ADR-007） */}
        {STATIC_ROUTES.map((route) => (
          <Route key={route.path} path={route.path} element={route.element} />
        ))}
        <Route path="403" element={<Forbidden />} />
        <Route path="*" element={<UnknownPath />} />
      </Route>
    </Routes>
  )
}

/**
 * 首页：跳到用户有权限的第一个菜单。
 *
 * ⚠️ 不能硬编码跳 /tickets —— no_role 用户没有任何菜单，
 *    硬跳过去会掉进 403，看起来像系统坏了。
 */
function HomeRedirect() {
  const menus = useAuthStore((s) => s.menus)

  const first = useMemo(() => {
    const walk = (nodes: typeof menus): string | null => {
      for (const n of nodes) {
        if (n.routePath) return n.routePath
        const child = walk(n.children)
        if (child) return child
      }
      return null
    }
    return walk(menus)
  }, [menus])

  if (!first) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#8c8c8c' }}>
        你还没有被分配任何菜单权限，请联系系统管理员。
      </div>
    )
  }

  return <Navigate to={first} replace />
}
