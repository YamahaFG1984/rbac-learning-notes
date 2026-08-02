import type { AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  configureVersionWatcher,
  resetVersionWatcher,
  watchRbacVersion,
} from '@/api/versionWatcher'
import { useAuthStore } from '@/auth/store'

function response(version?: string): AxiosResponse {
  return {
    headers: version ? { 'x-rbac-version': version } : {},
  } as unknown as AxiosResponse
}

function setPerms(perms: string[]) {
  useAuthStore.setState({ perms, status: 'authenticated' })
}

let refetchProfile: ReturnType<typeof vi.fn>
let notify: ReturnType<typeof vi.fn>

/**
 * ⚠️ mock 的形状必须和真实实现一致 —— 这里踩过一次。
 *
 *    第一版的 refetchProfile 返回 void，watcher 回头读 store 比对。
 *    单测里 mock 是**同步**改 store 的，所以一直是绿的；
 *    真实环境里 store 的写入走 useEffect，要等 React 重渲染，
 *    `await refetch()` 解决时 store 还是旧值 → 提示永远不弹。
 *
 *    **单测只能验证你写下的契约，不能验证这个契约本身是否成立。**
 *    那一层要靠 E2E（e2e/perm-change.spec.ts 抓到了它）。
 */
beforeEach(() => {
  resetVersionWatcher()
  setPerms(['ticket:ticket:view'])
  refetchProfile = vi.fn(async () => ({ perms: useAuthStore.getState().perms }))
  notify = vi.fn()
  configureVersionWatcher({ refetchProfile, notify })
})

describe('版本号变化的判定', () => {
  it('🔴 第一次收到版本号时不重拉 —— 否则会无限循环', async () => {
    // profile 请求本身也带回版本号。无条件 invalidate 的话：
    // profile 响应 → 版本号「变了」→ 重拉 profile → 又一个响应 → …
    await watchRbacVersion(response('1'))
    expect(refetchProfile).not.toHaveBeenCalled()
  })

  it('版本号没变时不重拉 —— 否则等于每个请求都拉一次 profile', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('1'))
    expect(refetchProfile).not.toHaveBeenCalled()
  })

  it('版本号变了才重拉', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))
    expect(refetchProfile).toHaveBeenCalledTimes(1)
  })

  it('没有这个响应头时什么都不做（模板版的响应）', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response())
    await watchRbacVersion(response('1'))
    expect(refetchProfile).not.toHaveBeenCalled()
  })
})

describe('提示的时机', () => {
  it('自己的权限真的变了才提示', async () => {
    refetchProfile.mockImplementation(async () => ({
      perms: ['ticket:ticket:view', 'ticket:ticket:delete'],
    }))

    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))

    expect(notify).toHaveBeenCalledWith('你的权限已更新')
  })

  it('🔴 别人的权限变了：重拉但**不提示**', async () => {
    // 全局版本号是粗粒度的（后端 ADR-010 的已知取舍）：
    // 任何人改权限，所有在线用户都会走到这里。
    // 一律提示的话，绝大多数人收到的都是误报。
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))

    expect(refetchProfile).toHaveBeenCalledTimes(1)
    expect(notify).not.toHaveBeenCalled()
  })

  it('perms 顺序不同不算变化', async () => {
    setPerms(['a', 'b'])
    refetchProfile.mockImplementation(async () => ({ perms: ['b', 'a'] }))

    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))

    expect(notify).not.toHaveBeenCalled()
  })

  it('权限被撤销（变少）也要提示', async () => {
    setPerms(['a', 'b'])
    refetchProfile.mockImplementation(async () => ({ perms: ['a'] }))

    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))

    expect(notify).toHaveBeenCalledWith('你的权限已更新')
  })
})

describe('登出重置', () => {
  it('🔴 不重置的话，下一个用户的第一个响应会被误判为「变了」', async () => {
    await watchRbacVersion(response('7'))

    // 登出 → 换人登录，服务端版本号没变，但 watcher 记着上一个会话的值
    resetVersionWatcher()
    await watchRbacVersion(response('9'))

    expect(refetchProfile).not.toHaveBeenCalled()
  })
})
