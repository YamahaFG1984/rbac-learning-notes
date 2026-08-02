import { defineConfig } from '@playwright/test'

/**
 * E2E 是唯一能验证这些的层（F-ADR-013）：
 *   · document.cookie 里没有 sessionid（jsdom 不实现 httpOnly）
 *   · 绕过前端直接调 API 仍被拒（需要真后端）
 *   · 动态路由在真实浏览器刷新后的行为
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'off',
  },
  projects: [{ name: 'chromium', use: { channel: undefined, headless: true } }],
})
