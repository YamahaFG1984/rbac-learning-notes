import { expect, test } from '@playwright/test'

import { login } from './helpers'
import { reseedDatabase } from './reseed'

test.beforeAll(reseedDatabase)
test.afterAll(reseedDatabase)

/**
 * 🎯 **整个前端权限体系的祛魅。**
 *
 * 这个文件要证明的不是「前端做得好」，而是
 * **「前端做的一切都可以被绕过，而系统依然安全」**。
 *
 * 前面三个 tag 做了三层体验（路由守卫、菜单、按钮），
 * 用 cs_staff 登录界面非常干净。**这份干净的安全价值是零。**
 * 下面四步依次证明。
 */
test.describe('🎯 前端权限全部可绕过，后端拦得住', () => {
  test('四步：隐藏了 → 可以改回来 → 改回来也没用 → 连前端都不用', async ({
    page,
  }) => {
    await login(page, 'cs_staff') // 只有 5 条工单，没有删除权限
    await page.goto('/tickets')

    // ── 第 1 步：前端确实隐藏了 ────────────────────────────────
    await expect(page.getByRole('heading', { name: '工单列表' })).toBeVisible()
    await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)

    // ── 第 2 步：把前端的权限判断整个改掉 ──────────────────────
    //
    // 攻击者在控制台做的就是这一步，耗时几秒。
    // 我们通过 window.__AUTH_STORE__ 表达它（只在 E2E 构建里挂），
    // 但他用 React DevTools 一样能做到，不需要这个变量。
    await page.evaluate(() => {
      const store = (window as unknown as Record<string, { setState: (s: unknown) => void }>)
        .__AUTH_STORE__
      store.setState({ perms: ['*'] })
    })

    const deleteButton = page
      .locator('.ant-table-tbody tr.ant-table-row')
      .first()
      .getByRole('button', { name: '删除' })

    // 按钮出现了 —— 路由守卫、菜单、按钮三层，没有一层挡得住
    await expect(deleteButton).toBeVisible()

    // ── 第 3 步：但真的点下去，后端拒绝 ────────────────────────
    const [response] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'DELETE' && r.url().includes('/api/v1/tickets/'),
      ),
      deleteButton.click().then(() =>
        page.locator('.ant-modal-confirm').getByRole('button', { name: '确定' }).click(),
      ),
    ])
    expect(response.status()).toBe(403)

    // ── 第 4 步：甚至不用这个前端 ──────────────────────────────
    //
    // page.request 完全绕过页面，用的是同一份 cookie 但不经过任何 React 代码。
    // 「攻击者不点你的按钮，他直接发请求」——SPA 版更进一步：
    // 「他连你的前端都不用。」
    const ids = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tickets/', { credentials: 'same-origin' })
      return (await res.json()).results.map((t: { id: number }) => t.id)
    })
    const direct = await page.request.delete(`/api/v1/tickets/${ids[0]}/`)
    expect(direct.status()).toBe(403)
  })

  test('🎯 篡改 store 也进不去无权限的页面（守卫失效，后端仍然拦）', async ({
    page,
  }) => {
    await login(page, 'cs_staff')
    await page.goto('/tickets')

    await page.evaluate(() => {
      const store = (window as unknown as Record<string, { setState: (s: unknown) => void }>)
        .__AUTH_STORE__
      store.setState({
        perms: ['*'],
        knownRoutes: ['/system/users'],
      })
    })

    // 路由守卫被绕过了（perms 变成通配），但页面上没有数据 ——
    // 因为菜单是后端下发的，动态路由压根没注册这个页面。
    // 就算注册了，接口也会 403。
    const status = await page.evaluate(
      async () => (await fetch('/api/v1/users/', { credentials: 'same-origin' })).status,
    )
    expect(status).toBe(403)
  })
})

/**
 * 🎯 F-ADR-002 的验收：会话凭证对 JS 不可见。
 *
 * ⚠️ 这件事**只能**在真浏览器里验证。
 *    jsdom 不实现 httpOnly 语义，在单测里 `document.cookie` 的断言是**假绿**——
 *    它会通过，但什么都没证明。
 */
test.describe('🎯 httpOnly Cookie', () => {
  test('document.cookie 里没有 sessionid，但有 csrftoken', async ({ page }) => {
    await login(page, 'cs_manager')

    const visible = await page.evaluate(() => document.cookie)
    expect(visible).not.toContain('sessionid')
    // ⚠️ csrftoken **必须**可读：SPA 要从 cookie 里读它放进 X-CSRFToken 头。
    //    把它设成 httpOnly 会让所有写请求 403，而且它本来就不是秘密（F-ADR-004）
    expect(visible).toContain('csrftoken')
  })

  test('浏览器确实持有 sessionid，且标了 httpOnly', async ({ page }) => {
    await login(page, 'cs_manager')

    const cookies = await page.context().cookies()
    const session = cookies.find((c) => c.name === 'sessionid')
    expect(session).toBeTruthy()
    expect(session?.httpOnly).toBe(true)
  })

  test('XSS 拿不到会话，但它仍然能直接发请求', async ({ page }) => {
    await login(page, 'cs_manager')

    // 模拟一段注入的脚本：它偷不到 sessionid……
    const stolen = await page.evaluate(() => document.cookie)
    expect(stolen).not.toContain('sessionid')

    // ……但它在同源里，浏览器会替它带上 cookie。
    // ⚠️ httpOnly 防的是「凭证被偷走异地复用」，
    //    **不防**「在受害者浏览器里以他的身份操作」。
    //    知道一个措施防的是什么，比知道它是个好措施重要。
    const status = await page.evaluate(
      async () => (await fetch('/api/v1/tickets/', { credentials: 'same-origin' })).status,
    )
    expect(status).toBe(200)
  })

  test('没有 CSRF token 的写请求被拒', async ({ page }) => {
    await login(page, 'cs_manager')

    const status = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tickets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ title: 'x' }),
      })
      return res.status
    })
    expect(status).toBe(403)
  })
})
