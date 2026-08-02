import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',
        'src/test/**',
        'src/**/*.d.ts',
        // 生成的常量文件，没有可测的逻辑
        'src/constants/permissions.ts',
      ],
      /*
       * 🔴 权限相关的模块要求 90%，和后端 apps/rbac ≥ 90% 是同一个标准。
       *
       * ⚠️ 覆盖率是**下限**不是目标。90% 的覆盖率不代表那 90% 测对了——
       *    真正守住权限的是 e2e/ 里的越权矩阵，不是这个数字。
       *    它的作用只是让「加了一个权限判断但没写测试」变得可见。
       */
      /*
       * ⚠️ 阈值是**按文件**定的，没有设全局 80%。这是一个需要说明的取舍。
       *
       *    规格书同时要求「src/router/** ≥ 90%」和「路由行为留给 E2E」
       *    （陷阱 6：jsdom 的 history 行为和真实浏览器有差异）。
       *    这两条是冲突的：AppRouter 的价值全在时序上，
       *    在 jsdom 里测它只会写出「测了但没测到」的假测试。
       *
       *    所以：**权限判断的逻辑**要 90%（下面这几个文件），
       *    **路由与页面的行为**交给 e2e/（58 条，跑在真浏览器 + 真后端上）。
       *
       *    全局覆盖率因此只有 ~25%，这个数字不好看但是诚实的：
       *    把 CRUD 页面用 jsdom 测一遍能把它推到 80%，
       *    但那些断言 e2e/admin-pages.spec.ts 已经用真后端做过了，
       *    重复一遍只增加维护成本，不增加任何保证。
       *
       *    **覆盖率是下限不是目标。90% 不代表那 90% 测对了。**
       */
      thresholds: {
        'src/auth/**': { statements: 90, branches: 85, functions: 90, lines: 90 },
        'src/router/PermissionGate.tsx': {
          statements: 90,
          branches: 90,
          functions: 90,
          lines: 90,
        },
        'src/router/buildRoutes.tsx': {
          statements: 85,
          branches: 90,
          functions: 60,
          lines: 85,
        },
        'src/utils/formErrors.ts': {
          statements: 90,
          branches: 90,
          functions: 90,
          lines: 90,
        },
        'src/components/Can.tsx': {
          statements: 90,
          branches: 90,
          functions: 90,
          lines: 90,
        },
        'src/api/errorHandlers.ts': {
          statements: 90,
          branches: 90,
          functions: 90,
          lines: 90,
        },
        'src/api/versionWatcher.ts': {
          statements: 90,
          branches: 85,
          functions: 90,
          lines: 90,
        },
      },
    },
  },
})
