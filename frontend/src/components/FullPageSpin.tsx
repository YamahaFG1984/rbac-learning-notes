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
      <Spin size="large" tip={tip}>
        <div style={{ padding: 24 }} />
      </Spin>
    </div>
  )
}
