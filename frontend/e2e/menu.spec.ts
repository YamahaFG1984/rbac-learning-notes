import { expect, test } from '@playwright/test'

import { login } from './helpers'

/**
 * 动态菜单的验收。
 *
 * 这里断言的全部是**后端过滤的结果**——前端一行权限判断都没有。
 * 如果哪天某个角色看到了不该看的菜单，问题一定在后端
 * get_user_menu_tree()，不在这一层。
 */
test.describe('动态菜单', () => {
  test('superadmin 看到全部四个目录', async ({ page }) => {
    await login(page, 'superadmin')
    const sider = page.locator('.ant-layout-sider')
    for (const name of ['工单管理', '组织管理', '权限管理', '系统监控']) {
      await expect(sider.getByText(name, { exact: true })).toBeVisible()
    }
  })

  test('cs_staff 只看到工单管理，看不到系统管理相关目录', async ({ page }) => {
    await login(page, 'cs_staff')
    const sider = page.locator('.ant-layout-sider')
    await expect(sider.getByText('工单管理', { exact: true })).toBeVisible()
    await expect(sider.getByText('组织管理', { exact: true })).toHaveCount(0)
    await expect(sider.getByText('权限管理', { exact: true })).toHaveCount(0)
  })

  test('no_role 看到的是说明文案，不是一片空白', async ({ page }) => {
    await login(page, 'no_role')
    await expect(
      page.locator('.ant-layout-sider').getByText('你还没有任何菜单权限'),
    ).toBeVisible()
  })

  test('🔴 在详情页 /tickets/42，「工单列表」仍然高亮', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets/42')
    await expect(
      page.locator('.ant-menu-item-selected').getByText('工单列表'),
    ).toBeVisible()
  })

  test('点目录只展开，不导航；点叶子才跳转', async ({ page }) => {
    await login(page, 'superadmin')
    const sider = page.locator('.ant-layout-sider')

    await sider.getByText('组织管理', { exact: true }).click()
    // 目录的 key 是 catalog-<id>，不该出现在地址栏里
    expect(page.url()).not.toContain('catalog-')

    await sider.getByText('部门管理', { exact: true }).click()
    await expect(page).toHaveURL(/\/system\/depts$/)
  })
})
