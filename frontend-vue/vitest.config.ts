import path from 'node:path'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/main.ts',
        'src/test/**',
        'src/**/*.d.ts',
        // 生成的常量文件，没有可测的逻辑
        'src/constants/permissions.ts',
        // ⚠️ 刻意保留但从不注册的反面教材（V-ADR-007）
        'src/directives/perm.ts',
      ],
      /*
       * 🔴 权限相关的模块要求 90%，和后端 apps/rbac ≥ 90% 是同一个标准。
       *
       * ⚠️ 覆盖率是**下限**不是目标。90% 的覆盖率不代表那 90% 测对了——
       *    真正守住权限的是 e2e/ 里的越权矩阵，不是这个数字。
       *    它的作用只是让「加了一个权限判断但没写测试」变得可见。
       *
       * 🟢 **沿用 React 版 `fe-v0.15.0` 的结论，不重走一遍那次纠结。**
       *
       *    那边发现规格书自相矛盾：一边要求「src/router/** ≥ 90%」，
       *    一边说「路由行为属于 E2E」。最终按文件设阈值 + 写明理由，
       *    整体覆盖率停在 ~25%。
       *
       *    Vue 版同样：**权限判断的逻辑**要 90%，
       *    **路由与页面的行为**交给 e2e/（跑在真浏览器 + 真后端上）。
       *
       *    ⚠️ VAC-7 也据此从 FAC-6 的「整体 ≥ 80%」改成了
       *       「权限相关模块 ≥ 90%」——**规格改了就改文档**。
       */
      thresholds: {
        'src/auth/**': { statements: 90, branches: 85, functions: 90, lines: 90 },
        'src/utils/formErrors.ts': {
          statements: 90, branches: 90, functions: 90, lines: 90,
        },
        'src/components/Can.vue': {
          statements: 90, branches: 90, functions: 90, lines: 90,
        },
        'src/api/errorHandlers.ts': {
          statements: 90, branches: 90, functions: 90, lines: 90,
        },
        'src/api/versionWatcher.ts': {
          statements: 90, branches: 85, functions: 90, lines: 90,
        },
        'src/layouts/menuAdapter.ts': {
          statements: 90, branches: 85, functions: 90, lines: 90,
        },
        'src/router/buildRoutes.ts': {
          statements: 85, branches: 85, functions: 60, lines: 85,
        },
      },
    },
  },
})
