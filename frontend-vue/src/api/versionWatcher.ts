import type { AxiosResponse } from 'axios'

import { useAuthStore } from '@/auth/store'

/**
 * 🔴 感知「我手里的权限快照过期了」。
 *
 * 后端每个 API 响应都带 `X-RBAC-Version`（全局版本号，v0.16.0 就有）。
 * 版本变了 = 有人改过权限 → 重拉 profile。
 *
 * 延迟正好是**一次 API 请求**，和后端 FR-4.5 的承诺对齐。
 *
 * 🟢 本文件的核心逻辑与 React 版**逐字相同**——它是纯逻辑，与框架无关。
 *    唯一的差异是 `before` 那一行，见下面的注释。
 */

/** 上一次见到的版本号。null 表示还没见过。 */
let lastSeen: string | null = null

/**
 * 由 App 注入，避免这里 import queryClient 造成循环依赖。
 *
 * ⚠️ `refetchProfile` 必须**返回拉到的新 profile**，不能只返回 void
 *    让调用方回头去读 store。
 *
 *    React 版的理由（fe-v0.13.0 真实踩过）：store 的写入走 `useEffect`，
 *    而 `useEffect` 要等重新渲染才跑，`await refetchQueries()` 解决的那一刻
 *    **store 里还是旧值**。表现是「按钮确实消失了，但提示永远不弹」。
 *
 *    📌 **Vue 版用 `watch` 做同一件事，这个窗口还在吗？**
 *       `vue-v0.11.0` 实测了，结论回填在 04 对比文档第 11 节。
 *       **无论结论如何，这里都保留「用返回值」的写法**——
 *       那条规则（「异步操作完成」≠「派生状态已更新」）是对的，
 *       即使某个框架的某个版本恰好让你侥幸过关。
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
 *    不重置的话，下一个用户登录时 `lastSeen` 还是上一个会话的值，
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

  /*
   * ⚠️📌 **`.slice()` 是防御性的，不是必需的——我一开始断言反了。**
   *
   *    初稿写的是「Vue 必须 slice，否则 Pinia 的响应式数组被原地改掉，
   *    比对永远相等、提示永远不弹」。**vue-v0.11.0 实测：不对。**
   *    去掉 slice 之后 `before` 仍然是旧值（6 个），提示照常弹出。
   *
   *    原因是 `store.setProfile` 写的是
   *        perms.value = profile.perms      ← **替换引用**
   *    而不是
   *        perms.value.splice(...)          ← 原地修改
   *
   *    **「Pinia 的 state 是可变的」不等于「你的代码在原地改它」**——
   *    取决于 setter 怎么写。我把「语言/框架允许什么」当成了「代码实际做什么」。
   *
   *    保留 slice 的理由变成纯防御：哪天有人把 setProfile 改成原地修改
   *    （`perms.value.length = 0; push(...)`），这一行就是唯一的护栏，
   *    而那种改动**不会有任何测试变红**。成本一次数组拷贝，值。
   */
  const auth = useAuthStore()
  const before = auth.perms.slice()

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
