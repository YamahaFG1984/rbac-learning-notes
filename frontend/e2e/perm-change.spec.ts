import { expect, test } from '@playwright/test'

import { login, revokePermission } from './helpers'
import { reseedDatabase } from './reseed'

// 本文件会撤销角色权限，前后各重置一次
test.beforeAll(reseedDatabase)
test.afterAll(reseedDatabase)

/**
 * 🔴 本 tag 的核心场景。这个问题在 Django 模板版**根本不存在**：
 *    模板版的界面和权限判断是同一次请求产生的，SPA 手里是一份快照。
 */
test.describe('🔴 权限变更感知', () => {
  test('撤权后，用户不刷新页面也会看到按钮消失', async ({ browser }) => {
    // 窗口 B：cs_manager 停在工单列表，删除按钮可见
    const userCtx = await browser.newContext()
    const user = await userCtx.newPage()
    await login(user, 'cs_manager')
    await user.goto('/tickets')

    const firstRow = user.locator('.ant-table-tbody tr.ant-table-row').first()
    await expect(firstRow.getByRole('button', { name: '删除' })).toBeVisible()

    // 窗口 A：管理员撤销「客服主管」的删除权限
    const adminCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    await login(admin, 'superadmin')
    await revokePermission(admin, 'cs_manager', 'ticket:ticket:delete')
    await adminCtx.close()

    // 窗口 B：**不刷新**，只是翻一页（一次普通的 API 请求）
    await user.getByTitle('2', { exact: true }).click()

    /*
     * ⚠️ 先断言**瞬时**的提示，再断言持久的状态。
     *
     *    AntD 的 message 3 秒后自动消失。反过来写的话，
     *    等「按钮消失」的那几秒里提示已经没了，
     *    报错是「找不到元素」——看起来像提示没弹，实际是弹完了。
     *
     *    异步 UI 的测试里，**断言顺序要按元素的存活时间从短到长排**。
     */
    await expect(user.getByText('你的权限已更新')).toBeVisible()

    // 版本号搭在这次响应上回来 → 重拉 profile → 按钮消失
    await expect(
      user.locator('.ant-table-tbody tr.ant-table-row').first().getByRole('button', {
        name: '删除',
      }),
    ).toHaveCount(0)

    // 全程没有 F5、没有重新登录
    expect(user.url()).toContain('/tickets')

    await userCtx.close()
  })

  test('🔴 别人的权限变了：重拉 profile，但不提示（避免误报）', async ({
    browser,
  }) => {
    const userCtx = await browser.newContext()
    const user = await userCtx.newPage()
    await login(user, 'cs_manager')
    await user.goto('/tickets')

    const adminCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    await login(admin, 'superadmin')
    // 改的是**别人**的角色 —— 全局版本号照样会 bump
    await revokePermission(admin, 'cs_specialist', 'ticket:ticket:update')
    await adminCtx.close()

    await user.getByTitle('2', { exact: true }).click()
    await user.waitForTimeout(1500)

    // 提示不该出现：全局版本号是粗粒度的，一律提示对绝大多数人是误报
    await expect(user.getByText('你的权限已更新')).toHaveCount(0)

    await userCtx.close()
  })

  test('版本号没变时不会反复重拉 profile', async ({ page }) => {
    let profileCalls = 0
    page.on('request', (req) => {
      if (req.url().includes('/api/v1/auth/profile/')) profileCalls += 1
    })

    await login(page, 'cs_manager')
    await page.goto('/tickets')
    await page.getByTitle('2', { exact: true }).click()
    await page.waitForTimeout(1000)

    const afterNav = profileCalls
    await page.getByTitle('1', { exact: true }).click()
    await page.waitForTimeout(1000)

    // 翻页不该触发新的 profile 请求 —— 第一次收到版本号就 invalidate 的话，
    // 这个数字会一直涨（而且是无限循环）
    expect(profileCalls).toBe(afterNav)
  })

  test('模板版的响应没有这个头（它每次都重算权限）', async ({ page }) => {
    await login(page, 'cs_manager')
    const headers = await page.evaluate(async () => {
      const api = await fetch('/api/v1/tickets/', { credentials: 'same-origin' })
      const tpl = await fetch('/django/tickets/', { credentials: 'same-origin' })
      return {
        api: api.headers.get('x-rbac-version'),
        tpl: tpl.headers.get('x-rbac-version'),
      }
    })
    expect(headers.api).not.toBeNull()
    expect(headers.tpl).toBeNull()
  })
})
