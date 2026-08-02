import type { AxiosError } from 'axios'

/**
 * 各状态码的处理策略。
 *
 * 从 client.ts 里抽出来，是为了让这张表**可以被单测**——
 * 「403 会不会跳登录页」这种事，值得有一条会跑的断言，
 * 而不是靠 code review 时有人注意到。
 */

interface Handlers {
  /** 跳登录页（已做并发去重） */
  redirectToLogin: () => void
  /** 重拉 profile —— 403 可能意味着权限刚被撤销 */
  refetchProfile: () => void
  warn: (text: string) => void
  error: (text: string) => void
}

let handlers: Handlers | null = null

export function configureErrorHandlers(next: Handlers) {
  handlers = next
}

/** 后端 DRF 的错误体是 `{"detail": "..."}` */
type ErrorBody = { detail?: string } | undefined

/**
 * 前端做的处理。返回值只用于测试断言，运行时没人看。
 *
 * `'unhandled'` 表示**故意不处理**，交给调用方。
 */
export type ErrorAction =
  | 'network'
  | 'unauthenticated'
  | 'forbidden'
  | 'unhandled'
  | 'throttled'
  | 'server'

export function handleApiError(error: AxiosError<ErrorBody>): ErrorAction {
  /*
   * ⚠️ 没有 response = 请求根本没到服务器。
   *
   *    把它显示成「服务器错误」会让用户去联系 IT，
   *    而真实原因可能只是他的 WiFi 断了。
   */
  if (!error.response) {
    handlers?.error('网络连接失败，请检查网络后重试')
    return 'network'
  }

  const { status, data } = error.response
  const detail = data?.detail

  switch (status) {
    case 401:
      /*
       * 401 = 「我不知道你是谁」→ 需要重新认证。
       *
       * ⚠️ **静默**，不弹提示：用户马上就会看到登录页，
       *    再弹一个红色的「请求失败」是纯噪音。
       *    会话过期时页面上可能有 5 个请求同时 401——
       *    每个弹一个，用户看到一片红然后被跳走。
       */
      handlers?.redirectToLogin()
      return 'unauthenticated'

    case 403:
      /*
       * 🔴 403 = 「我知道你是谁，但你不能做这个」。
       *
       *    **绝不跳登录页。** 这是 SPA 里的高频 bug，一个字之差：
       *
       *        if (status === 401 || status === 403) redirectToLogin()
       *
       *    后果是死循环：
       *        点了无权限的按钮 → 403 → 跳登录 → 重新登录 → 还是 403 → …
       *
       *    用户会以为账号坏了、密码错了、系统崩了——
       *    而真实原因只是「他确实没这个权限」。重新登录解决不了任何事。
       *
       * ⚠️ 403 必须**出声**（与 401 相反）：页面不会变，
       *    不提示的话用户完全不知道刚才发生了什么。
       */
      handlers?.warn(detail ?? '权限不足')
      // 兜底：可能是权限刚被撤销（fe-v0.13.0 的版本号方案有盲区）
      handlers?.refetchProfile()
      return 'forbidden'

    case 404:
      /*
       * ⚠️ **故意不处理**，原样抛给调用方。
       *
       *    404 的正确处理取决于场景：
       *      · 详情页加载失败 → 整页替换成 ResourceNotFound
       *      · 列表页某个操作 404 → 提示 + 刷新列表（那条可能刚被删）
       *      · 后台静默请求 → 可能什么都不用做
       *
       *    全局统一弹 toast 的话，详情页会**既停在空白上又弹个提示**。
       */
      return 'unhandled'

    case 429:
      // 后端已经写了人话（「登录失败次数过多，请 15 分钟后再试」），
      // 前端再硬编码一套是浪费，而且两边会漂移
      handlers?.warn(detail ?? '操作过于频繁，请稍后再试')
      return 'throttled'

    default:
      if (status >= 500) {
        /*
         * ⚠️ 5xx **不弹 toast**。
         *
         *    500 意味着服务端炸了，页面上的数据可能是半截的。
         *    弹个 toast 然后让用户继续在坏掉的界面上点，比整页替换更糟。
         *    整页替换由 AppErrorBoundary + Query 的全局 onError 负责。
         */
        return 'server'
      }
      // 其余 4xx（主要是 400 表单校验）交给调用方映射到字段上
      return 'unhandled'
  }
}
