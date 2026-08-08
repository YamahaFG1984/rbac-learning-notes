import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import 'ant-design-vue/dist/reset.css'
import './index.css'

/**
 * ⚠️ 与 React 版 main.tsx 的 QueryClient 配置**逐字对应**。
 *    这些是缓存与重试策略，跟框架无关。
 */
const vueQueryOptions = {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        // 权限相关的数据不该被「窗口聚焦」这类事件随意重取，
        // 它只应由版本号变化或显式 invalidate 触发（vue-v0.11.0）
        refetchOnWindowFocus: false,
        /*
         * ⚠️ 只重试网络层的失败，不重试 4xx。
         *
         *    403 重试三次仍然是 403，只是让用户多等两秒；
         *    404 同理。默认的 retry: 3 在权限系统里纯粹是噪音，
         *    还会把「一次越权尝试」放大成审计日志里的四条 perm_denied。
         */
        retry: (failureCount: number, error: unknown) => {
          const status = (error as { response?: { status?: number } }).response?.status
          if (status && status >= 400 && status < 500) return false
          return failureCount < 1
        },
      },
      mutations: {
        /*
         * 🔴 写请求**绝不自动重试**。
         *
         *    网络超时不代表服务端没收到——重试可能创建出两张工单。
         *    读请求重试最多浪费一次流量，写请求重试会产生副作用。
         */
        retry: false,
      },
    },
  },
}

const app = createApp(App)

/*
 * ⚠️ **注册顺序：pinia 必须在 router 之前。**
 *
 *    router/index.ts 的守卫里要调 useAuthStore()。router 一旦被 use，
 *    首次导航会立刻触发守卫——那时 pinia 必须已经就绪。
 *
 *    顺序写反的报错是
 *        getActivePinia() was called with no active Pinia
 *    ⚠️ 实测：Pinia 4 的报错明确写着 "before calling app.use(pinia)"，
 *       直接指向时机问题。表现是整页白屏——**失败得很响**。
 *
 *    这是 V-ADR-003 那类问题的现场：Pinia 的 store 绑在 app 实例上，
 *    而 React 版的 Zustand 是模块级单例，
 *    **根本不存在「什么时候可以用 store」这个问题。**
 */
app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin, vueQueryOptions)

/*
 * 🔴 **刻意不写 `app.use(Antd)`。**
 *
 *    那是 Vue + Ant Design Vue 最常见的写法，也是 vue-v0.1.0 实测到的第一个真实问题：
 *    全局注册**所有**组件 → tree-shaking 失效。
 *
 *    实测（vue-v0.1.0，只有一个占位页）：
 *        Vue   dist/assets 合计 **1.53 MB**   ← app.use(Antd)
 *        React dist/assets 合计 **1.24 MB**   ← 12 个页面、全部功能
 *        Vue   改成按需 import 后 **0.51 MB**
 *
 *    正确做法是在用到的地方按需 import（antdv 4 是 CSS-in-JS，样式自动跟随）。
 *    V-ADR-002（最小差异原则）也要求这一处对齐 React 版的
 *    `import { Button } from 'antd'`——否则 vue-v1.0.0 的体积对比
 *    量出来的是「注册方式的差异」，而不是「框架的差异」。
 *
 *    📌 详见 04-React与Vue3做法对比.md 第 16 节。
 */

app.mount('#app')
