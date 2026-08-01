import { expect, test } from '@playwright/test'

import { login } from './helpers'

/**
 * fe-v0.7.0 的时序用例。
 *
 * ⚠️ 这些**必须**在真浏览器里测——jsdom 的 history 行为与真实浏览器有差异，
 *    在单测里写这些断言会得到「假绿」。
 */
test.describe('动态路由的时序', () => {
  test('🔴 在详情页刷新不会 404', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')
    await expect(page.getByRole('heading', { name: '工单列表' })).toBeVisible()

    // 直接进详情页再刷新——路由表是动态注册的，
    // AppRouter 若不在 AuthBootstrap 内部，这里会掉进 404
    await page.goto('/tickets/1')
    await page.reload()
    await expect(page.getByRole('heading', { name: '工单详情' })).toBeVisible()
  })

  test('🔴 未登录直达受保护 URL，登录后回到原地址', async ({ page }) => {
    await page.goto('/tickets')
    await expect(page).toHaveURL(/\/login\?redirect=/)

    await page.getByLabel('用户名').fill('cs_manager')
    await page.getByLabel('密码').fill('demo1234')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page).toHaveURL(/\/tickets$/)
  })

  test('🔴 无权限路径跳 403，不是 404', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/system/users')

    // 路径存在（在 knownRoutes 里）但当前用户无权限 → 403
    await expect(page.getByText('403')).toBeVisible()
    await expect(page.getByText('404')).toHaveCount(0)
  })

  test('不存在的路径跳 404，不是 403', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/no-such-page')

    await expect(page.getByText('404')).toBeVisible()
  })

  test('no_role 用户：首页给出说明而不是 403 或白屏', async ({ page }) => {
    await login(page, 'no_role')
    await expect(page.getByText('你还没有被分配任何菜单权限')).toBeVisible()
  })

  test('open redirect 被挡住', async ({ page }) => {
    await page.goto('/login?redirect=//evil.example')
    await page.getByLabel('用户名').fill('cs_manager')
    await page.getByLabel('密码').fill('demo1234')
    await page.getByRole('button', { name: '登录' }).click()

    await page.waitForURL((url) => !url.pathname.startsWith('/login'))
    expect(page.url()).toContain('localhost:5173')
    expect(page.url()).not.toContain('evil.example')
  })
})

test.describe('F-ADR-002 的验收', () => {
  test('🎯 会话凭证对 JS 不可见', async ({ page, context }) => {
    await login(page, 'cs_manager')

    const jsVisible = await page.evaluate(() => document.cookie)
    expect(jsVisible).not.toContain('sessionid')
    expect(jsVisible).toContain('csrftoken') // 这个必须可读（F-ADR-004）

    const cookies = await context.cookies()
    const session = cookies.find((c) => c.name === 'sessionid')
    expect(session?.httpOnly).toBe(true)
  })
})
