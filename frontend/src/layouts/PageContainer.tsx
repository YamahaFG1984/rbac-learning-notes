import type { ReactNode } from 'react'

import { Space, Typography } from 'antd'

/**
 * 页面外壳：标题 + 右侧操作区 + 内容。
 *
 * 对应模板版的 {% block page_title %} / {% block page_actions %} / {% block content %}。
 * 模板用继承实现复用，React 用组合。
 */
interface Props {
  title: ReactNode
  extra?: ReactNode
  children: ReactNode
}

export function PageContainer({ title, extra, children }: Props) {
  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        <Space>{extra}</Space>
      </div>
      {children}
    </>
  )
}
