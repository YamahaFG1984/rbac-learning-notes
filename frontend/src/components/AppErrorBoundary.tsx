import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback: (reset: () => void) => ReactNode
}

interface State {
  error: Error | null
}

/**
 * 渲染期错误的兜底。
 *
 * ⚠️ React 的 Error Boundary **只捕获渲染期错误**：
 *    渲染函数、生命周期、构造函数里抛出的异常。
 *
 *    它捕获不到：
 *      · 事件处理器里的异常
 *      · setTimeout / Promise 回调
 *      · 服务端返回的 5xx（那是数据不是异常）
 *
 *    所以「服务端炸了」这件事需要 QueryClient 的全局 onError 配合，
 *    不能指望这一个组件。**边界只是最后一道，不是唯一一道。**
 *
 * ⚠️ 为什么 5xx 走整页替换而不是 toast：
 *    500 意味着服务端炸了，页面上的数据可能是半截的。
 *    弹个 toast 然后让用户继续在坏掉的界面上点，比整页替换更糟——
 *    他会以为「只是这一次失败了」，接着基于错误的数据做决定。
 *
 * ⚠️ 必须仍然是 class 组件。React 到今天也没有 hook 版的 Error Boundary，
 *    这是极少数 hook 覆盖不到的场景。
 */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 生产环境这里接监控。开发环境至少让它出现在控制台里——
    // 被边界兜住的错误默认不会打断执行，很容易被忽略掉。
    console.error('[AppErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return this.props.fallback(() => this.setState({ error: null }))
    }
    return this.props.children
  }
}
