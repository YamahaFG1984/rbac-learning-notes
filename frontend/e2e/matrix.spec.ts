import { expect, test, type Page } from '@playwright/test'

import { login } from './helpers'
import { reseedDatabase } from './reseed'

// ⚠️ 「直调 API」那一段真的会删掉工单，跑完必须还原 ——
//    否则下一个 spec 文件里的 80/50/5 就对不上了。
test.beforeAll(reseedDatabase)
test.afterAll(reseedDatabase)

/**
 * 🎯 越权矩阵：**可执行的权限规格说明书**。
 *
 * 对照后端 tests/test_permission_matrix.py —— 但这不是重复劳动。
 *
 *   后端矩阵测的是「API 的行为」
 *   这里测的是「**用户实际看到什么**」
 *
 * 两者之间可能不一致，而不一致的地方正是 SPA 特有的 bug：
 *
 *   | 后端对 | 前端错 | 表现 |
 *   | API 返回 50 条 | 前端多过滤一次 | 用户看到 40 条 |
 *   | API 403 | 前端跳登录页 | 死循环 |
 *   | 菜单接口正确 | 前端渲染错 | 菜单少一项 |
 *
 * **E2E 测的就是这个「之间」。**
 */

// ─────────────────────────────────────────────────────────────
// 功能权限：谁能进哪个页面
// ─────────────────────────────────────────────────────────────

type Access = 'ok' | 'forbidden'

const PAGE_MATRIX: Array<{
  role: string
  path: string
  heading: string
  expect: Access
}> = [
  // 用户管理
  { role: 'superadmin', path: '/system/users', heading: '用户管理', expect: 'ok' },
  { role: 'sysadmin', path: '/system/users', heading: '用户管理', expect: 'ok' },
  { role: 'cs_manager', path: '/system/users', heading: '用户管理', expect: 'forbidden' },
  { role: 'cs_staff', path: '/system/users', heading: '用户管理', expect: 'forbidden' },
  { role: 'no_role', path: '/system/users', heading: '用户管理', expect: 'forbidden' },
  // 角色管理
  { role: 'superadmin', path: '/system/roles', heading: '角色管理', expect: 'ok' },
  { role: 'sysadmin', path: '/system/roles', heading: '角色管理', expect: 'ok' },
  { role: 'cs_manager', path: '/system/roles', heading: '角色管理', expect: 'forbidden' },
  // 审计日志
  { role: 'sysadmin', path: '/monitor/audit', heading: '审计日志', expect: 'ok' },
  { role: 'cs_manager', path: '/monitor/audit', heading: '审计日志', expect: 'forbidden' },
  // 工单列表
  { role: 'cs_staff', path: '/tickets', heading: '工单列表', expect: 'ok' },
  { role: 'no_role', path: '/tickets', heading: '工单列表', expect: 'forbidden' },
]

test.describe('功能权限矩阵：页面可达性', () => {
  for (const { role, path, heading, expect: access } of PAGE_MATRIX) {
    test(`${role} 访问 ${path} → ${access}`, async ({ page }) => {
      await login(page, role)
      await page.goto(path)

      if (access === 'ok') {
        await expect(page.getByRole('heading', { name: heading })).toBeVisible()
      } else {
        // ⚠️ 期望的是 **403 页面**，不是白屏、不是 404、更不是登录页。
        //    跳登录页会造成「登录 → 403 → 登录」的死循环（fe-v0.14.0）。
        await expect(page.getByText('403')).toBeVisible()
        await expect(page.getByRole('heading', { name: heading })).toHaveCount(0)
        await expect(page).not.toHaveURL(/\/login/)
      }
    })
  }
})

// ─────────────────────────────────────────────────────────────
// 数据权限：谁看到几条
// ─────────────────────────────────────────────────────────────

/** 🎯 必须与后端 tests/test_permission_matrix.py 的 SCOPE_MATRIX 完全一致 */
const SCOPE_MATRIX: Array<[string, number]> = [
  ['superadmin', 80],
  ['sysadmin', 80],
  ['cs_manager', 50],
  ['cs_staff', 5],
]

test.describe('数据权限矩阵：谁看到几条', () => {
  for (const [role, count] of SCOPE_MATRIX) {
    test(`${role} 的工单列表显示 ${count} 条`, async ({ page }) => {
      await login(page, role)
      await page.goto('/tickets')

      // 页面显示的总数 == 后端返回的 count。
      // 不相等就说明某一层多做了事（FNFR-5：前端不做二次过滤）
      await expect(page.getByText(`共 ${count} 条`)).toBeVisible()
    })
  }

  test('跨部门的工单：404 而不是 403（不泄露存在性）', async ({ browser }) => {
    // 先用超管拿一个技术部工单的真实 id
    const adminCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    await login(admin, 'superadmin')
    const techId = await admin.evaluate(async () => {
      const res = await fetch('/api/v1/tickets/?kw=技术部', {
        credentials: 'same-origin',
      })
      return (await res.json()).results[0].id as number
    })
    await adminCtx.close()

    const ctx = await browser.newContext()
    const page = await ctx.newPage()
    await login(page, 'cs_manager')
    await page.goto(`/tickets/${techId}`)

    // 后端 ADR-009：范围外返回 404 而不是 403 —— 403 会泄露「这条记录存在」
    await expect(page.getByText('不存在或你无权访问')).toBeVisible()
    await ctx.close()
  })
})

// ─────────────────────────────────────────────────────────────
// 🔴 直调 API：这一段完全不依赖前端
// ─────────────────────────────────────────────────────────────

/** 拿一个该用户数据范围内的工单 id */
async function firstVisibleTicketId(page: Page): Promise<number | null> {
  return page.evaluate(async () => {
    const res = await fetch('/api/v1/tickets/', { credentials: 'same-origin' })
    if (!res.ok) return null
    const data = await res.json()
    return data.results[0]?.id ?? null
  })
}

/**
 * 🔴 直调写接口时**必须带上 CSRF token**。
 *
 * 不带的话 Django 一律返回 403 —— 于是：
 *   · 期望 403 的那几行会「通过」，但**是因为错误的原因**
 *   · 期望 204 的那几行会失败，报错指向权限，真实原因是 CSRF
 *
 * 我在 fe-v0.9.0 写下过这条规则，这里自己又踩了一次：
 *
 *   > 一个鉴权测试如果因为请求根本没到达权限判断那一步而通过，
 *   > 它是**假绿**——比没有测试更糟，因为它给人安全感。
 *
 * 「无 CSRF 的写请求被拒」是**另一件事**，由 bypass.spec.ts 单独测。
 * 一条测试只测一件事，否则你分不清它到底在测什么。
 */
async function csrfHeaders(page: Page) {
  const cookies = await page.context().cookies()
  const token = cookies.find((c) => c.name === 'csrftoken')?.value ?? ''
  return { 'X-CSRFToken': token }
}

/**
 * 🔴 矩阵最后两行**必须独立成立**。
 *
 * 用 page.request 完全绕过页面：同一份 cookie，但不经过任何 React 代码。
 *
 * 这一段和上面「删除按钮可见性」那一段**逻辑一致但互相独立**：
 *   · 前端哪天改错了 —— 这里仍然是绿的
 *   · 后端哪天改错了 —— 这里立刻变红
 *
 * 通过点按钮来测「后端拦不拦」是自欺欺人：那测的还是前端。
 */
test.describe('🔴 直调 API（绕过前端）', () => {
  const DELETE_MATRIX: Array<[string, number[]]> = [
    // 有 delete 权限，且工单在范围内 → 204
    ['superadmin', [204]],
    ['cs_manager', [204]],
    // 没有 delete 权限 → 403
    ['sysadmin', [403]],
    ['cs_staff', [403]],
  ]

  for (const [role, allowed] of DELETE_MATRIX) {
    test(`${role} 直接 DELETE 自己范围内的工单 → ${allowed.join('/')}`, async ({
      page,
    }) => {
      await login(page, role)
      await page.goto('/tickets')

      const id = await firstVisibleTicketId(page)
      expect(id).not.toBeNull()

      const res = await page.request.delete(`/api/v1/tickets/${id}/`, {
        headers: await csrfHeaders(page),
      })
      expect(allowed).toContain(res.status())
    })
  }

  test('no_role 连列表都读不到（默认拒绝）', async ({ page }) => {
    await login(page, 'no_role')
    const res = await page.request.get('/api/v1/tickets/')
    expect(res.status()).toBe(403)
  })

  test('未登录时是 401 而不是 403（两者语义不同）', async ({ request }) => {
    const res = await request.get('/api/v1/tickets/')
    // DRF 加上 SessionAuthentication 后会把 401 降级成 403，
    // 后端专门修正了这一点（F-ADR-011）：SPA 必须严格区分这两者
    expect(res.status()).toBe(401)
  })
})

// ─────────────────────────────────────────────────────────────
// 菜单：谁看到几个目录
// ─────────────────────────────────────────────────────────────

test.describe('菜单矩阵', () => {
  const MENU_MATRIX: Array<[string, string[], string[]]> = [
    ['superadmin', ['工单管理', '组织管理', '权限管理', '系统监控'], []],
    ['sysadmin', ['组织管理', '权限管理', '系统监控'], []],
    ['cs_manager', ['工单管理'], ['组织管理', '权限管理', '系统监控']],
    ['cs_staff', ['工单管理'], ['组织管理', '权限管理']],
  ]

  for (const [role, visible, hidden] of MENU_MATRIX) {
    test(`${role} 的菜单`, async ({ page }) => {
      await login(page, role)
      const sider = page.locator('.ant-layout-sider')

      for (const name of visible) {
        await expect(sider.getByText(name, { exact: true })).toBeVisible()
      }
      for (const name of hidden) {
        await expect(sider.getByText(name, { exact: true })).toHaveCount(0)
      }
    })
  }

  test('no_role 的菜单为空，但有说明文案而不是白屏', async ({ page }) => {
    await login(page, 'no_role')
    await expect(
      page.locator('.ant-layout-sider').getByText('你还没有任何菜单权限'),
    ).toBeVisible()
  })
})
