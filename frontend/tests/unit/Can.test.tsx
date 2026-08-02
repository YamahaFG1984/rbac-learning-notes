import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/auth/store'
import { Can } from '@/components/Can'
import { PERM } from '@/constants/permissions'

function givePerms(perms: string[]) {
  useAuthStore.setState({ perms, status: 'authenticated' })
}

beforeEach(() => {
  useAuthStore.setState({ perms: [], status: 'unknown' })
})

describe('<Can>', () => {
  it('有权限时渲染 children', () => {
    givePerms([PERM.TICKET_TICKET_DELETE])
    render(
      <Can perm={PERM.TICKET_TICKET_DELETE}>
        <button>删除</button>
      </Can>,
    )
    expect(screen.getByText('删除')).toBeTruthy()
  })

  it('无权限时什么都不渲染', () => {
    givePerms([PERM.TICKET_TICKET_VIEW])
    render(
      <Can perm={PERM.TICKET_TICKET_DELETE}>
        <button>删除</button>
      </Can>,
    )
    expect(screen.queryByText('删除')).toBeNull()
  })

  it('无权限时渲染 fallback', () => {
    givePerms([])
    render(
      <Can perm={PERM.TICKET_TICKET_EXPORT} fallback={<span>需要导出权限</span>}>
        <button>导出</button>
      </Can>,
    )
    expect(screen.queryByText('导出')).toBeNull()
    expect(screen.getByText('需要导出权限')).toBeTruthy()
  })

  it("超管的 ['*'] 通配生效", () => {
    givePerms(['*'])
    render(
      <Can perm={PERM.SYSTEM_ROLE_ASSIGN_PERM}>
        <button>分配权限</button>
      </Can>,
    )
    expect(screen.getByText('分配权限')).toBeTruthy()
  })

  it('anyOf：任一满足即渲染', () => {
    givePerms([PERM.TICKET_TICKET_UPDATE])
    render(
      <Can anyOf={[PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_UPDATE]}>
        <button>操作</button>
      </Can>,
    )
    expect(screen.getByText('操作')).toBeTruthy()
  })

  it('allOf：缺一个就不渲染', () => {
    givePerms([PERM.TICKET_TICKET_UPDATE])
    render(
      <Can allOf={[PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_UPDATE]}>
        <button>操作</button>
      </Can>,
    )
    expect(screen.queryByText('操作')).toBeNull()
  })

  it('🔴 什么都不传时不渲染 —— 默认拒绝，写漏了立刻可见', () => {
    givePerms(['*'])
    render(
      <Can>
        <button>危险</button>
      </Can>,
    )
    // 即使是超管也不渲染：没声明权限 = 配置错误，不是「不限制」
    expect(screen.queryByText('危险')).toBeNull()
  })

  it('写错的权限码是**编译期**错误，不是静默不渲染', () => {
    // @ts-expect-error 'ticket:ticket:delet' 不在 PermCode 里 —— 这行如果不报错，
    // 说明 perm 的类型被写成了 string，SPA 唯一比模板版强的地方就丢了（F-ADR-012）
    void (<Can perm="ticket:ticket:delet">x</Can>)
  })
})

/**
 * 🔴 本 tag 存在的真正理由。
 *
 * 上面所有测试证明的都只是「按钮不出现」——**这不等于操作被阻止**。
 * 隐藏按钮是体验优化，唯一的安全边界在后端。
 */
describe('🔴 隐藏 ≠ 阻止', () => {
  it('把 perms 改成 ["*"] 就能让按钮全部出现（前端确实挡不住）', () => {
    givePerms([])
    const { rerender } = render(
      <Can perm={PERM.TICKET_TICKET_DELETE}>
        <button>删除</button>
      </Can>,
    )
    expect(screen.queryByText('删除')).toBeNull()

    // 攻击者在控制台做的就是这一步，耗时几秒
    givePerms(['*'])
    rerender(
      <Can perm={PERM.TICKET_TICKET_DELETE}>
        <button>删除</button>
      </Can>,
    )
    expect(screen.getByText('删除')).toBeTruthy()

    // ⚠️ 这条测试**通过**才是对的。前端权限不是安全机制。
    //    「点了这个按钮会不会真的删掉」由后端 HasPerm 决定，
    //    单测碰不到它 —— 见 fe-v0.16.0 的越权矩阵 E2E。
  })
})
