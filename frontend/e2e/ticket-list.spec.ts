import { expect, test } from '@playwright/test'

import { login } from './helpers'

/** 必须与后端 tests/test_permission_matrix.py 的 SCOPE_MATRIX 完全一致 */
const SCOPE_MATRIX: Array<[string, number]> = [
  ['superadmin', 80],
  ['sysadmin', 80],
  ['cs_manager', 50],
  ['cs_staff', 5],
]

test.describe('工单列表的数据权限', () => {
  for (const [username, expected] of SCOPE_MATRIX) {
    test(`${username} 看到 ${expected} 条`, async ({ page }) => {
      await login(page, username)
      await page.goto('/tickets')
      // 分页器的 total 直接来自后端 count —— 前端不重新计算
      await expect(page.getByText(`共 ${expected} 条`)).toBeVisible()
    })
  }

  test('🔴 前端渲染的行数 == 后端返回的条数（没有二次过滤）', async ({ page }) => {
    await login(page, 'cs_staff')

    const [payload] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/api/v1/tickets/?') && r.status() === 200,
      ),
      page.goto('/tickets'),
    ])
    const { count, results } = await payload.json()

    const rows = page.locator('.ant-table-tbody tr.ant-table-row')
    await expect(rows).toHaveCount(results.length)
    expect(count).toBe(5)
  })
})

test.describe('分页与筛选', () => {
  test('翻页写进 URL，刷新后保持', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')

    await page.getByTitle('2', { exact: true }).click()
    await expect(page).toHaveURL(/[?&]page=2/)

    await page.reload()
    // 刷新后仍然停在第 2 页，而不是跳回第 1 页
    await expect(page.locator('.ant-pagination-item-active')).toHaveText('2')
  })

  test('筛选条件写进 URL，且会把页码重置回 1', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets?page=3')

    await page.getByPlaceholder('搜索标题或内容').fill('单')
    await page.getByPlaceholder('搜索标题或内容').press('Enter')

    await expect(page).toHaveURL(/kw=/)
    // 不重置的话会停在第 3 页，筛出的结果不足 3 页时显示「暂无数据」
    await expect(page).not.toHaveURL(/page=3/)
  })

  test('🔴 分享带筛选的链接：条件一样，数据按各自权限', async ({ browser }) => {
    const url = '/tickets?status=open'

    const managerCtx = await browser.newContext()
    const managerPage = await managerCtx.newPage()
    await login(managerPage, 'cs_manager')
    await managerPage.goto(url)
    const managerTotal = await managerPage
      .locator('.ant-pagination-total-text')
      .textContent()

    const staffCtx = await browser.newContext()
    const staffPage = await staffCtx.newPage()
    await login(staffPage, 'cs_staff')
    await staffPage.goto(url)
    const staffTotal = await staffPage
      .locator('.ant-pagination-total-text')
      .textContent()

    // 同一个 URL，同一套筛选条件，不同的可见范围。
    // URL 里带什么参数都改变不了后端的 .for_user()。
    expect(managerTotal).not.toBe(staffTotal)

    await managerCtx.close()
    await staffCtx.close()
  })
})

test.describe('导出', () => {
  test('cs_staff 看不到导出按钮，直接调接口也是 403', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')
    await expect(page.getByRole('button', { name: '导出' })).toHaveCount(0)

    const status = await page.evaluate(
      async () => (await fetch('/api/v1/tickets/export/')).status,
    )
    expect(status).toBe(403)
  })

  test('🎯 导出行数 == 列表 count', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')
    await expect(page.getByText('共 50 条')).toBeVisible()

    const csv = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tickets/export/')
      return res.text()
    })
    const dataRows = csv.trim().split('\n').slice(1).filter(Boolean)

    // 导出是最容易被忽略的越权入口：它是后加的功能，代码路径和列表页不同。
    expect(dataRows).toHaveLength(50)
  })
})
