import type { Page } from '@playwright/test'

export const PASSWORD = 'demo1234'

export async function login(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 10_000 })
}

/**
 * 用管理员身份撤掉某个角色的某个权限。
 *
 * ⚠️ 只提交 `checked && !inherited` 的节点 —— 这正是前端真实的提交逻辑
 *    （继承来的权限属于父角色，不该出现在子角色的提交值里）。
 */
export async function revokePermission(
  admin: Page,
  roleCode: string,
  permCode: string,
) {
  await admin.evaluate(
    async ({ roleCode, permCode }) => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const roles = await (
        await fetch('/api/v1/roles/', { credentials: 'same-origin' })
      ).json()
      const role = (roles.results ?? roles).find(
        (r: { code: string }) => r.code === roleCode,
      )

      const payload = await (
        await fetch(`/api/v1/roles/${role.id}/permissions/`, {
          credentials: 'same-origin',
        })
      ).json()

      const keep = payload.nodes
        .filter(
          (n: { checked: boolean; inherited: boolean; code: string | null }) =>
            n.checked && !n.inherited && n.code !== permCode,
        )
        .map((n: { id: number }) => n.id)

      await fetch(`/api/v1/roles/${role.id}/permissions/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ permissions: keep }),
      })
    },
    { roleCode, permCode },
  )
}
