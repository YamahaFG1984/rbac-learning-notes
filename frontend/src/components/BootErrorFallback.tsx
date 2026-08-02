import { Button, Result } from 'antd'

/**
 * 应用级错误的兜底页。
 *
 * ⚠️ 不能复用 ErrorResult —— 那个组件用了 useNavigate，
 *    而这里在 BrowserRouter **外面**（错误可能就发生在路由初始化时）。
 *    在路由上下文之外调用 useNavigate 会再抛一个错误，
 *    于是错误边界的 fallback 自己也炸了，用户看到彻底的白屏。
 *
 *    **兜底组件的依赖必须比它兜的东西更少。**
 */
export function BootErrorFallback({ onRetry }: { onRetry: () => void }) {
  return (
    <Result
      status="500"
      title="页面出错了"
      subTitle="发生了预期之外的错误。可以重试，若反复出现请联系管理员。"
      extra={
        <>
          <Button type="primary" onClick={onRetry}>
            重试
          </Button>
          <Button onClick={() => window.location.assign('/')}>返回首页</Button>
        </>
      }
    />
  )
}
