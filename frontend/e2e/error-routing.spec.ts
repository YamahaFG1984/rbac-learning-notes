import { expect, test } from '@playwright/test'

import { login, revokePermission } from './helpers'
import { reseedDatabase } from './reseed'

/*
 * ⚠️ beforeEach 而不是 beforeAll —— 本文件的第一条用例会撤销
 *    cs_manager 的**查看**权限，同文件后面的用例就拿不到列表数据了
 *    （分页按钮根本不渲染，报错是「点不到元素」，指不到真正原因）。
 *
 *    fe-v0.12.0 遇到的是**跨文件**的同一个问题。
 *    共享可变状态的污染范围，取决于你在哪一层重置，不取决于你的意图。
 */
test.beforeEach(reseedDatabase)
test.afterAll(reseedDatabase)

/**
 * 🔴 本文件的核心是前两条：403 绝不跳登录页。
 *
 * 一个字之差（`status === 401 || status === 403`）就会造成死循环：
 * 点了无权限的按钮 → 403 → 跳登录 → 重新登录 → 还是 403 → …
 * 用户会以为账号坏了，而真实原因只是「他确实没这个权限」。
 */
test.describe('🔴 403 不是 401', () => {
  test('权限被撤销后，UI 发出的请求 403：提示 + 留在当前页', async ({
    browser,
  }) => {
    const userCtx = await browser.newContext()
    const user = await userCtx.newPage()
    await login(user, 'cs_manager')
    await user.goto('/tickets')

    // 管理员撤掉「客服主管」的**查看**权限 —— 之后他的任何列表请求都会 403
    const adminCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    await login(admin, 'superadmin')
    await revokePermission(admin, 'cs_manager', 'ticket:ticket:view')
    await adminCtx.close()

    // 用 UI 触发一次真实的、经过 axios 拦截器的请求
    await user.getByTitle('2', { exact: true }).click()

    // 🔴 关键：**没有**被踢到登录页
    await user.waitForTimeout(2000)
    await expect(user).not.toHaveURL(/\/login/)
    expect(user.url()).toContain('/tickets')

    await userCtx.close()
  })

  test('🔴 会话没过期时，403 绝不把人踢到登录页', async ({ page }) => {
    await login(page, 'cs_staff')
    // /system/roles 这个页面 cs_staff 无权访问，进去会渲染 403 页
    await page.goto('/system/roles')

    await expect(page.getByText('403')).toBeVisible()
    // 关键断言：**没有**跳登录页
    await expect(page).not.toHaveURL(/\/login/)

    // 而且刷新之后还是 403，不是被踢出去
    await page.reload()
    await expect(page.getByText('403')).toBeVisible()
    await expect(page).not.toHaveURL(/\/login/)
  })
})

test.describe('401 的处理', () => {
  test('会话失效后跳登录页，并带上原地址', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')
    // ⚠️ 必须等页面**渲染完**再清 cookie。
    //    清早了的话首屏请求就 401 了，页面直接跳走，
    //    后面 click 找不到分页按钮 —— 报错是「点不到元素」，
    //    看起来像选择器写错，实际是时序。
    const nextPage = page.getByTitle('2', { exact: true })
    await expect(nextPage).toBeVisible()

    // 手工清掉会话 cookie，模拟会话过期
    await page.context().clearCookies({ name: 'sessionid' })

    // 触发一次 API 请求
    await nextPage.click()

    await expect(page).toHaveURL(/\/login\?redirect=/)
  })

  test('🔴 多个请求同时 401，只跳一次，URL 不嵌套', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')
    const nextPage = page.getByTitle('2', { exact: true })
    await expect(nextPage).toBeVisible()

    await page.context().clearCookies({ name: 'sessionid' })

    await nextPage.click()
    await page.waitForURL(/\/login/)
    await page.waitForTimeout(800)

    const url = page.url()
    // 不去重的话会变成 /login?redirect=/login?redirect=/login...
    expect(url.match(/redirect=/g)?.length ?? 0).toBe(1)
    expect(url).not.toContain('redirect=%2Flogin')
  })
})

test.describe('404 由调用方处理，不做全局 toast', () => {
  test('详情页整页替换，不弹提示', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets/999999')

    await expect(page.getByText('不存在或你无权访问')).toBeVisible()
    // 全局统一弹 toast 的话，这里会**既是空白页又有个提示**
    await expect(page.locator('.ant-message')).toHaveCount(0)
  })
})

test.describe('400 映射到表单，不弹全局 toast', () => {
  test('登录密码错误时错误显示在表单里', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('用户名').fill('cs_staff')
    await page.getByLabel('密码').fill('wrong-password')
    await page.getByRole('button', { name: '登录' }).click()

    // 后端的 detail 被显示出来，而不是前端硬编码一句「登录失败」
    await expect(page.getByText(/用户名或密码/)).toBeVisible()
    await expect(page).toHaveURL(/\/login/)
  })
})
