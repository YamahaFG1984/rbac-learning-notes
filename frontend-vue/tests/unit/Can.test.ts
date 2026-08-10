import { render, screen } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { h, nextTick } from 'vue'

import { useAuthStore } from '@/auth/store'
import Can from '@/components/Can.vue'
import { PERM } from '@/constants/permissions'
import { PROFILES } from '@/test/fixtures'

beforeEach(() => setActivePinia(createPinia()))

const renderCan = (props: Record<string, unknown>) =>
  render(Can, {
    props,
    slots: { default: () => h('button', '删除'), fallback: () => h('span', '无权限') },
  })

describe('<Can> —— 按钮级权限', () => {
  it('有权限时渲染 children', () => {
    useAuthStore().setProfile(PROFILES.cs_manager)
    renderCan({ perm: PERM.TICKET_TICKET_DELETE })
    expect(screen.getByRole('button', { name: '删除' })).toBeInTheDocument()
  })

  it('无权限时渲染 fallback', () => {
    useAuthStore().setProfile(PROFILES.cs_staff)
    renderCan({ perm: PERM.TICKET_TICKET_DELETE })
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()
    expect(screen.getByText('无权限')).toBeInTheDocument()
  })

  it('🔴 什么都不传时**不渲染**（默认拒绝在前端的形态）', () => {
    useAuthStore().setProfile(PROFILES.superadmin)
    renderCan({})
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()
  })

  it('anyOf / allOf', () => {
    useAuthStore().setProfile(PROFILES.cs_staff)
    const a = renderCan({ anyOf: [PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_VIEW] })
    expect(a.getByRole('button', { name: '删除' })).toBeInTheDocument()
    a.unmount()

    const b = renderCan({ allOf: [PERM.TICKET_TICKET_DELETE, PERM.TICKET_TICKET_VIEW] })
    expect(b.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()
  })

  it('🔴 权限运行时变化后按钮会消失 / 恢复（ok 是 computed）', async () => {
    const auth = useAuthStore()
    auth.setProfile(PROFILES.cs_manager)
    renderCan({ perm: PERM.TICKET_TICKET_DELETE })
    expect(screen.getByRole('button', { name: '删除' })).toBeInTheDocument()

    /*
     * ⚠️ Vue 的 DOM 更新在 nextTick —— 时序是**确定的**。
     *    React 版这里要 `await waitFor(...)` 轮询等待。
     *
     *    但 Vue 的确定性有上限：链路里若是「watch 触发 watch」，
     *    一个 nextTick 不够，表现是「断言偶尔失败」。
     *    遇到就用 flushPromises，**不要靠加 nextTick 凑数**。
     */
    auth.perms = ['ticket:ticket:view']
    await nextTick()
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()

    // 🎯 这一条是 v-perm 指令方案做不到的（V-ADR-007 缺陷 2）
    auth.perms = ['*']
    await nextTick()
    expect(screen.getByRole('button', { name: '删除' })).toBeInTheDocument()
  })
})
