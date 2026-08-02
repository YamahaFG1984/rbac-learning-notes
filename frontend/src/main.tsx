import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import App from './App.tsx'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { BootErrorFallback } from './components/BootErrorFallback'
import './index.css'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 权限相关的数据不该被「窗口聚焦」这类事件随意重取，
      // 它只应由版本号变化或显式 invalidate 触发（fe-v0.13.0）
      refetchOnWindowFocus: false,
      /*
       * ⚠️ 只重试网络层的失败，不重试 4xx。
       *
       *    403 重试三次仍然是 403，只是让用户多等两秒；
       *    404 同理。默认的 retry: 3 在权限系统里纯粹是噪音，
       *    还会把「一次越权尝试」放大成审计日志里的四条 perm_denied。
       */
      retry: (failureCount, error) => {
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
  mutationCache: new MutationCache({
    // mutation 的失败已经在 axios 拦截器里分流过了，这里不重复处理。
    // 留一个空壳是为了将来接监控时有地方挂。
  }),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/*
      ⚠️ autoInsertSpace 默认为 true：AntD 会给「登录」这类两个汉字的按钮
         自动插入空格，渲染成「登 录」。

         后果是任何按文本查找按钮的代码都失效——测试里
         getByRole('button', { name: '登录' }) 找不到元素，
         而报错只说「找不到」，完全指不到真正原因。

         关掉它，让 DOM 里的文本和源码里写的一致。
    */}
    <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
      <AntdApp>
        <QueryClientProvider client={queryClient}>
          {/*
            ⚠️ 错误边界放在 QueryClientProvider **内部**：
               fallback 里的重试按钮需要能重置 Query 的状态。
               放外面的话，重试只是重新渲染一次同样失败的组件。
          */}
          <AppErrorBoundary
            fallback={(reset) => (
              <BootErrorFallback
                onRetry={() => {
                  queryClient.clear()
                  reset()
                }}
              />
            )}
          >
            <App />
          </AppErrorBoundary>
        </QueryClientProvider>
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)
