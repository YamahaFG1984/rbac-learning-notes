import { expect, test } from '@playwright/test'

import { login } from './helpers'
import { reseedDatabase } from './reseed'

// 本文件会改角色权限、数据范围，并写入审计日志。前后各重置一次。
test.beforeAll(reseedDatabase)
test.afterAll(reseedDatabase)

test.describe('管理页的可达性', () => {
  test('sysadmin 能进四个管理页', async ({ page }) => {
    await login(page, 'sysadmin')
    for (const [path, title] of [
      ['/system/depts', '部门管理'],
      ['/system/users', '用户管理'],
      ['/system/roles', '角色管理'],
      ['/system/perms', '权限点'],
      ['/monitor/audit', '审计日志'],
    ]) {
      await page.goto(path)
      await expect(page.getByRole('heading', { name: title })).toBeVisible()
    }
  })

  test('cs_manager 菜单里没有，直接输 URL 跳 403', async ({ page }) => {
    await login(page, 'cs_manager')
    const sider = page.locator('.ant-layout-sider')
    await expect(sider.getByText('组织管理', { exact: true })).toHaveCount(0)

    await page.goto('/system/roles')
    // ⚠️ 断言的是**内容**不是 URL：403 页在原地渲染，地址栏保持
    //    /system/roles 不变——这样链接仍可分享、刷新仍然有效。
    //    改写地址会让用户失去「我刚才想去哪」这个信息。
    await expect(page.getByText('403')).toBeVisible()
    await expect(page.getByRole('heading', { name: '角色管理' })).toHaveCount(0)
  })
})

test.describe('🔴 角色权限树的继承标记', () => {
  test('纯继承的权限灰显且不可勾选', async ({ page }) => {
    await login(page, 'superadmin')
    await page.goto('/system/roles')

    await page
      .getByRole('row', { name: /客服主管/ })
      .getByRole('button', { name: '配置权限' })
      .click()

    const modal = page.locator('.ant-modal')
    await expect(modal.getByText(/本角色继承自「客服专员」/)).toBeVisible()

    // 「新建工单」来自客服专员，对主管是纯继承
    const inheritedNode = modal
      .locator('.ant-tree-treenode')
      .filter({ hasText: 'ticket:ticket:create' })
    await expect(inheritedNode.getByText('继承')).toBeVisible()
    await expect(inheritedNode.locator('.ant-tree-checkbox-disabled')).toBeVisible()
  })

  test('角色自己的权限可以正常取消勾选', async ({ page }) => {
    await login(page, 'superadmin')
    await page.goto('/system/roles')
    await page
      .getByRole('row', { name: /客服主管/ })
      .getByRole('button', { name: '配置权限' })
      .click()

    // delete 是主管自己的，不带「继承」标签，也不禁用
    const ownNode = page
      .locator('.ant-modal .ant-tree-treenode')
      .filter({ hasText: 'ticket:ticket:delete' })
    await expect(ownNode.getByText('继承')).toHaveCount(0)
    await expect(ownNode.locator('.ant-tree-checkbox-disabled')).toHaveCount(0)
  })
})

test.describe('🔴 权限不可放大（ADR-011）', () => {
  test('sysadmin 授不出自己没有的角色，界面上就是灰的', async ({ page }) => {
    await login(page, 'sysadmin')
    await page.goto('/system/users')

    await page
      .getByRole('row', { name: /no_role/ })
      .getByRole('button', { name: '分配角色' })
      .click()

    const modal = page.locator('.ant-modal')
    await expect(modal.getByText('有些角色你授不出去')).toBeVisible()
    // 客服主管含 sysadmin 自己没有的 ticket:ticket:delete
    await expect(
      modal.locator('.ant-checkbox-wrapper-disabled').filter({ hasText: '客服主管' }),
    ).toBeVisible()
  })

  test('绕开界面直接 PUT 也授不出去 —— 灰色 checkbox 不是安全边界', async ({
    page,
  }) => {
    await login(page, 'sysadmin')
    await page.goto('/system/users')

    const result = await page.evaluate(async () => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const users = await (
        await fetch('/api/v1/users/?page_size=100', { credentials: 'same-origin' })
      ).json()
      const target = (users.results ?? users).find(
        (u: { username: string }) => u.username === 'no_role',
      )
      const roles = await (
        await fetch('/api/v1/roles/?page_size=100', { credentials: 'same-origin' })
      ).json()
      const manager = (roles.results ?? roles).find(
        (r: { code: string }) => r.code === 'cs_manager',
      )

      const res = await fetch(`/api/v1/users/${target.id}/roles/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ roles: [manager.id] }),
      })
      return res.json()
    })

    expect(result.rejected).toBeGreaterThan(0)
    expect(result.saved).toBe(0)
  })
})

test.describe('数据范围', () => {
  test('选「自定义」才出现部门树，且写明包含下级', async ({ page }) => {
    await login(page, 'superadmin')
    await page.goto('/system/roles')

    await page
      .getByRole('row', { name: /客服主管/ })
      .getByRole('button', { name: '数据范围' })
      .click()

    const modal = page.locator('.ant-modal')
    await expect(modal.locator('.ant-tree')).toHaveCount(0)

    await modal.getByText('自定义部门').click()
    await expect(modal.locator('.ant-tree')).toBeVisible()
    await expect(modal.getByText(/包含其所有下级/)).toBeVisible()
  })
})

test.describe('用户表单', () => {
  test('🔴 没有 is_superuser 字段', async ({ page }) => {
    await login(page, 'sysadmin')
    await page.goto('/system/users')
    await page.getByRole('button', { name: '新建用户' }).click()

    const modal = page.locator('.ant-modal')
    await expect(modal.getByLabel('用户名')).toBeVisible()
    // 安全红线 4：有这个字段的话，任何有 system:user:update 的人
    // 都能一次点击把自己变成超管
    await expect(modal.getByText('超级管理员')).toHaveCount(0)
    await expect(modal.getByText('is_superuser')).toHaveCount(0)
  })
})

test.describe('权限点页与审计日志', () => {
  test('权限点页只读，没有任何编辑按钮', async ({ page }) => {
    await login(page, 'sysadmin')
    await page.goto('/system/perms')

    await expect(page.getByText('权限点由代码声明，此页只读')).toBeVisible()
    for (const name of ['新建', '编辑', '删除']) {
      await expect(page.getByRole('button', { name })).toHaveCount(0)
    }
  })

  test('🔴 审计日志把 added / removed 渲染成可读的标签', async ({ page }) => {
    await login(page, 'superadmin')

    // 先制造一次权限变更
    await page.goto('/system/roles')
    await page.evaluate(async () => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const roles = await (
        await fetch('/api/v1/roles/?page_size=100', { credentials: 'same-origin' })
      ).json()
      const target = (roles.results ?? roles).find(
        (r: { code: string }) => r.code === 'empty',
      )
      const perms = await (
        await fetch('/api/v1/permissions/?page_size=500', {
          credentials: 'same-origin',
        })
      ).json()
      const view = (perms.results ?? perms).find(
        (p: { code: string }) => p.code === 'ticket:ticket:view',
      )
      await fetch(`/api/v1/roles/${target.id}/permissions/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ permissions: [view.id] }),
      })
    })

    await page.goto('/monitor/audit')
    // 不是一坨 JSON，而是能一眼看出「加了什么」的标签
    await expect(
      page.locator('.ant-tag').filter({ hasText: '+ ticket:ticket:view' }).first(),
    ).toBeVisible()
  })

  test('🔴 改数据范围会留下审计记录（曾经完全没有）', async ({ page }) => {
    await login(page, 'superadmin')
    await page.goto('/system/roles')

    await page.evaluate(async () => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const roles = await (
        await fetch('/api/v1/roles/?page_size=100', { credentials: 'same-origin' })
      ).json()
      const target = (roles.results ?? roles).find(
        (r: { code: string }) => r.code === 'empty',
      )
      await fetch(`/api/v1/roles/${target.id}/data-scope/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ dataScope: 1, departments: [] }),
      })
    })

    await page.goto('/monitor/audit')
    await expect(page.getByText('设置数据范围').first()).toBeVisible()
  })
})
