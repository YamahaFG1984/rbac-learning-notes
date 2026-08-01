import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import App from './App.tsx'
import './index.css'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 权限相关的数据不该被「窗口聚焦」这类事件随意重取，
      // 它只应由版本号变化或显式 invalidate 触发（fe-v0.13.0）
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
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
          <App />
        </QueryClientProvider>
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)
