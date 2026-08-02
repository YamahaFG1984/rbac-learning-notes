import type { AxiosResponse } from 'axios'

import { useAuthStore } from '@/auth/store'

/**
 * 🔴 感知「我手里的权限快照过期了」。
 *
 * 后端每个 API 响应都带 `X-RBAC-Version`（全局版本号，v0.16.0 就有）。
 * 版本变了 = 有人改过权限 → 重拉 profile。
 *
 * 延迟正好是**一次 API 请求**，和后端 FR-4.5 的承诺对齐。
 */

/** 上一次见到的版本号。null 表示还没见过。 */
let lastSeen: string | null = null

/**
 * 由 App 注入，避免这里 import queryClient 造成循环依赖。
 *
 * ⚠️ refetchProfile 必须**返回拉到的新 profile**，不能只返回 void
 *    让调用方回头去读 store。
 *
 *    原因是时序：store 的写入走的是 useProfileQuery 里的 useEffect，
 *    而 useEffect 要等 React 重新渲染才跑。
 *    `await refetchQueries()` 解决的那一刻，**store 里还是旧值**。
 *
 *    我第一版就是读 store 比对的，结果是：按钮确实消失了
 *    （React 后来渲染了），但提示永远不弹（比对时新旧一样）。
 *    这个 bug 只在 E2E 里能发现——单测里 mock 的 refetch 是同步改 store 的。
 *
 *    规则：**「异步操作完成」和「派生状态已更新」是两件事。**
 *    需要用结果做判断时，就直接用返回值，不要绕道去读状态。
 */
let refetchProfile: (() => Promise<{ perms: string[] } | undefined>) | null = null
let notify: ((message: string) => void) | null = null

export function configureVersionWatcher(options: {
  refetchProfile: () => Promise<{ perms: string[] } | undefined>
  notify: (message: string) => void
}) {
  refetchProfile = options.refetchProfile
  notify = options.notify
}

/**
 * ⚠️ 登出时必须调用。
 *
 *    不重置的话，下一个用户登录时 lastSeen 还是上一个会话的值，
 *    第一个响应就会被判定为「版本变了」，白白多拉一次 profile。
 */
export function resetVersionWatcher() {
  lastSeen = null
}

function sameSet(a: string[], b: string[]) {
  if (a.length !== b.length) return false
  const set = new Set(a)
  return b.every((x) => set.has(x))
}

export async function watchRbacVersion(response: AxiosResponse) {
  const version = response.headers['x-rbac-version'] as string | undefined
  if (!version) return

  /*
   * ⚠️ 两个条件缺一不可：
   *
   *   lastSeen !== null  —— **第一次**收到版本号时不能 invalidate。
   *                         那时 profile 刚拉完，再拉一次是浪费；
   *                         而且 profile 请求本身也带回版本号，
   *                         无条件 invalidate 会形成**无限循环**。
   *
   *   version !== lastSeen —— 没变就什么都不做。每次响应都 invalidate
   *                           等价于「每个请求都重拉一次 profile」。
   */
  const changed = lastSeen !== null && version !== lastSeen
  lastSeen = version

  if (!changed || !refetchProfile) return

  const before = useAuthStore.getState().perms
  const fresh = await refetchProfile()
  if (!fresh) return
  const after = fresh.perms

  /*
   * ⚠️ 版本号是**全局**的（后端 ADR-010 的已知取舍）：
   *    任何人改权限，所有在线用户都会走到这里。
   *
   *    所以不能一律提示「你的权限已更新」——那对绝大多数人是误报。
   *    重拉之后比对新旧 perms，真的变了才提示。
   */
  if (!sameSet(before, after)) {
    notify?.('你的权限已更新')
  }
}
