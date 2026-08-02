import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { useAuthStore } from '@/auth/store'
import { PERM } from '@/constants/permissions'
import { PermissionGate } from '@/router/PermissionGate'

function renderAt(perm: Parameters<typeof PermissionGate>[0]['perm']) {
  return render(
    <MemoryRouter initialEntries={['/x']}>
      <Routes>
        <Route
          path="/x"
          element={
            <PermissionGate perm={perm}>
              <div>页面内容</div>
            </PermissionGate>
          }
        />
        <Route path="/403" element={<div>403 页</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PermissionGate', () => {
  it('有权限时渲染子节点', () => {
    useAuthStore.setState({ perms: [PERM.TICKET_TICKET_VIEW] })
    renderAt(PERM.TICKET_TICKET_VIEW)
    expect(screen.getByText('页面内容')).toBeTruthy()
  })

  it('无权限时跳 403', () => {
    useAuthStore.setState({ perms: [] })
    renderAt(PERM.TICKET_TICKET_VIEW)
    expect(screen.getByText('403 页')).toBeTruthy()
    expect(screen.queryByText('页面内容')).toBeNull()
  })

  it('perm 为 null（catalog 或不受控页面）时直接放行', () => {
    useAuthStore.setState({ perms: [] })
    renderAt(null)
    expect(screen.getByText('页面内容')).toBeTruthy()
  })

  it("超管的 ['*'] 通配放行", () => {
    useAuthStore.setState({ perms: ['*'] })
    renderAt(PERM.SYSTEM_ROLE_ASSIGN_PERM)
    expect(screen.getByText('页面内容')).toBeTruthy()
  })

  it('🔴 改一下 store 就能进去 —— 这条测试通过才是对的', () => {
    useAuthStore.setState({ perms: [] })
    const { unmount } = renderAt(PERM.SYSTEM_USER_VIEW)
    expect(screen.getByText('403 页')).toBeTruthy()
    unmount()

    // 攻击者在控制台做的就是这一步，耗时几秒
    useAuthStore.setState({ perms: ['*'] })
    renderAt(PERM.SYSTEM_USER_VIEW)

    // ⚠️ 断言「进去了」是**故意**的：路由守卫不是安全边界。
    //    它挡的是误操作和坏链接，不是攻击者。
    //    真正的边界在后端，由 fe-v0.16.0 的越权矩阵证明。
    expect(screen.getByText('页面内容')).toBeTruthy()
  })
})
