import { Spin } from 'antd'

export function FullPageSpin({ tip = '加载中' }: { tip?: string }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* AntD 6 起 Spin 的 tip 已废弃，改用 description */}
      <Spin size="large" description={tip}>
        <div style={{ padding: 24 }} />
      </Spin>
    </div>
  )
}
