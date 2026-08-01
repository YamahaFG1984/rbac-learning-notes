import { expect, test } from '@playwright/test'

import { login } from './helpers'

test.describe('按钮级权限', () => {
  test('cs_manager 看得到删除 / 派单 / 导出', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')
    for (const name of ['派单', '导出']) {
      await expect(page.getByRole('button', { name })).toBeVisible()
    }
    await expect(page.getByRole('button', { name: '删除' })).toBeVisible()
  })

  test('cs_staff 看不到删除 / 派单 / 导出', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')
    // 先等页面确实渲染出来，否则「找不到」只是因为还没加载完
    await expect(page.getByRole('heading', { name: '工单列表' })).toBeVisible()
    for (const name of ['派单', '导出', '删除']) {
      await expect(page.getByRole('button', { name })).toHaveCount(0)
    }
  })

  test('superadmin 的 * 通配让全部按钮可见', async ({ page }) => {
    await login(page, 'superadmin')
    await page.goto('/tickets')
    for (const name of ['新建工单', '派单', '导出']) {
      await expect(page.getByRole('button', { name })).toBeVisible()
    }
  })
})

/**
 * 🔴 本 tag 的核心结论，拆成两半验证：
 *
 *   前半（按钮会不会出现）—— tests/unit/Can.test.tsx「隐藏 ≠ 阻止」
 *      把 perms 改成 ['*']，按钮**确实全部出现**。前端挡不住。
 *
 *   后半（操作会不会成功）—— 这里。绕开整个前端直接发请求。
 *      攻击者不点你的按钮，在 SPA 里他连你的前端都不用。
 */
test.describe('🔴 隐藏 ≠ 阻止', () => {
  test('cs_staff 绕开前端直接 DELETE，后端 403', async ({ page }) => {
    await login(page, 'cs_staff')

    const status = await page.evaluate(async () => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const res = await fetch('/api/v1/tickets/1/', {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrf },
        credentials: 'same-origin',
      })
      return res.status
    })

    // 403（无权限）或 404（数据权限之外，ADR-009 不暴露存在性）都算挡住了。
    // 唯独不能是 204。
    expect([403, 404]).toContain(status)
  })

  test('cs_manager 同样的请求不会被权限拦住（对照组）', async ({ page }) => {
    await login(page, 'cs_manager')

    const status = await page.evaluate(async () => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const res = await fetch('/api/v1/tickets/999999/', {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrf },
        credentials: 'same-origin',
      })
      return res.status
    })

    // 用一个不存在的 id：有权限时应当止步于 404（找不到），
    // 而不是 403（没权限）。这条对照组保证上一条测的是**权限**，
    // 不是「所有人都删不掉」这种无意义的全绿。
    expect(status).toBe(404)
  })
})
