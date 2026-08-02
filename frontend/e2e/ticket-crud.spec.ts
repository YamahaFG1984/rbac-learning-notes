import { expect, test } from '@playwright/test'

import { login } from './helpers'
import { reseedDatabase } from './reseed'

// 本文件会新建和删除工单。跑完还原，不把污染留给后面的文件。
test.afterAll(reseedDatabase)

/** 技术部的工单 id —— 不在客服部任何人的数据范围内 */
async function outOfScopeTicketId(page: import('@playwright/test').Page) {
  const payload = await page.evaluate(async () => {
    const res = await fetch('/api/v1/tickets/?kw=技术部', {
      credentials: 'same-origin',
    })
    return res.json()
  })
  return payload.results[0].id as number
}

test.describe('🔴 数据权限在详情页的表现', () => {
  test('范围外的工单：整页「不存在或你无权访问」，不泄露存在性', async ({
    browser,
  }) => {
    // 先用能看到技术部工单的人拿一个真实存在的 id
    const adminCtx = await browser.newContext()
    const adminPage = await adminCtx.newPage()
    await login(adminPage, 'superadmin')
    await adminPage.goto('/tickets')
    const id = await outOfScopeTicketId(adminPage)
    await adminCtx.close()

    const ctx = await browser.newContext()
    const page = await ctx.newPage()
    await login(page, 'cs_staff')
    await page.goto(`/tickets/${id}`)

    await expect(page.getByText('不存在或你无权访问')).toBeVisible()
    // 🔴 绝不能出现「工单不存在」——那等于告诉用户这个 id 是空的，
    //    后端 ADR-009 返回 404 而不是 403 的努力就白费一半了
    await expect(page.getByText('工单不存在')).toHaveCount(0)
    await expect(page.getByText('无权限')).toHaveCount(0)

    await ctx.close()
  })

  test('不存在的 id：文案完全一样，两种情况分不出来', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets/999999')
    await expect(page.getByText('不存在或你无权访问')).toBeVisible()
  })

  test('范围内的工单正常渲染', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')
    await page.locator('.ant-table-tbody tr.ant-table-row a').first().click()
    await expect(page.getByText('创建人')).toBeVisible()
  })
})

test.describe('新建与编辑', () => {
  test('表单里没有创建人 / 归属部门字段', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')
    await page.getByRole('button', { name: '新建工单' }).click()

    const modal = page.locator('.ant-modal')
    await expect(modal.getByText('标题')).toBeVisible()
    // 它们由后端从 request.user 快照，界面上没有任何地方能改
    await expect(modal.getByLabel('创建人')).toHaveCount(0)
    await expect(modal.getByLabel('归属部门')).toHaveCount(0)
  })

  test('新建成功后 department 由后端快照为自己的部门', async ({ page }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')

    await page.getByRole('button', { name: '新建工单' }).click()
    const modal = page.locator('.ant-modal')
    await modal.getByLabel('标题').fill('E2E 新建的工单')
    await modal.getByRole('button', { name: '确定' }).click()

    await expect(page.getByText('工单已创建')).toBeVisible()
    // cs_staff 在客服一组
    await expect(page.getByText('客服一组').first()).toBeVisible()
  })

  test('🔴 后端的字段错误映射回表单，不是弹一个笼统的失败提示', async ({
    page,
  }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')
    await page.getByRole('button', { name: '新建工单' }).click()

    const modal = page.locator('.ant-modal')
    // 超长标题：前端不复制「128 字符」这条规则，让后端说
    await modal.getByLabel('标题').fill('长'.repeat(200))
    await modal.getByRole('button', { name: '确定' }).click()

    // 错误显示在标题这一项下面，而不是一个全局 toast
    await expect(modal.locator('.ant-form-item-explain-error')).toBeVisible()
  })
})

test.describe('🔴 派单候选人不能泄露用户名册', () => {
  test('cs_manager 的候选人只有客服部的人', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')

    const names = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tickets/assignable-users/', {
        credentials: 'same-origin',
      })
      return (await res.json()).map((u: { username: string }) => u.username)
    })

    expect(new Set(names)).toEqual(
      new Set(['cs_manager', 'cs_staff', 'no_role']),
    )
    // 技术部同事和超管都不在里面
    expect(names).not.toContain('techie')
    expect(names).not.toContain('superadmin')
  })

  test('cs_manager 没有 system:user:view，却拿得到候选人', async ({ page }) => {
    await login(page, 'cs_manager')
    const statuses = await page.evaluate(async () => {
      const users = await fetch('/api/v1/users/', { credentials: 'same-origin' })
      const candidates = await fetch('/api/v1/tickets/assignable-users/', {
        credentials: 'same-origin',
      })
      return [users.status, candidates.status]
    })
    // 复用 /users/ 的话，「能派单」就被迫要求「能管用户」——权限点会被倒逼变粗
    expect(statuses).toEqual([403, 200])
  })

  test('🔴 下拉框不是安全边界：直接提交范围外的 assignee 被拒', async ({
    browser,
  }) => {
    // 技术部同事的 id。攻击者遍历几下就能拿到，这里为了测试稳定直接查出来
    const adminCtx = await browser.newContext()
    const adminPage = await adminCtx.newPage()
    await login(adminPage, 'superadmin')
    const techieId = await adminPage.evaluate(async () => {
      const res = await fetch('/api/v1/users/', { credentials: 'same-origin' })
      const payload = await res.json()
      const rows = payload.results ?? payload
      return rows.find((u: { username: string }) => u.username === 'techie').id
    })
    await adminCtx.close()

    const ctx = await browser.newContext()
    const page = await ctx.newPage()
    await login(page, 'cs_manager')
    await page.goto('/tickets')

    const result = await page.evaluate(async (assignee) => {
      const list = await (
        await fetch('/api/v1/tickets/', { credentials: 'same-origin' })
      ).json()
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const res = await fetch(`/api/v1/tickets/${list.results[0].id}/assign/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ assignee }),
      })
      return { status: res.status, body: await res.text() }
    }, techieId)

    expect(result.status).toBe(400)
    expect(result.body).toContain('不在你可指派的范围内')

    await ctx.close()
  })
})

test.describe('删除', () => {
  test('删除要二次确认，确认后列表刷新且分页数字正确', async ({ page }) => {
    await login(page, 'cs_manager')
    await page.goto('/tickets')

    const before = Number(
      (await page.locator('.ant-pagination-total-text').textContent())!.replace(
        /\D/g,
        '',
      ),
    )

    await page
      .locator('.ant-table-tbody tr.ant-table-row')
      .first()
      .getByRole('button', { name: '删除' })
      .click()
    await expect(page.getByText('此操作不可撤销')).toBeVisible()
    await page.locator('.ant-modal-confirm').getByRole('button', { name: '确定' }).click()

    await expect(page.getByText('工单已删除')).toBeVisible()
    // ⚠️ 本地删行的话这个数字不会变 —— 分页和计数的真相在后端
    await expect(page.getByText(`共 ${before - 1} 条`)).toBeVisible()
  })
})
