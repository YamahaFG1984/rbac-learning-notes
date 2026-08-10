import type { AxiosResponse } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  configureVersionWatcher,
  resetVersionWatcher,
  watchRbacVersion,
} from '@/api/versionWatcher'
import { useAuthStore } from '@/auth/store'

function response(version?: string): AxiosResponse {
  return { headers: version ? { 'x-rbac-version': version } : {} } as unknown as AxiosResponse
}

let refetchProfile: ReturnType<typeof vi.fn>
let notify: ReturnType<typeof vi.fn>

/**
 * ⚠️ **mock 的形状必须和真实实现一致 —— React 版在这里踩过一次。**
 *
 *    它第一版的 refetchProfile 返回 void，watcher 回头读 store 比对。
 *    单测里 mock 是**同步**改 store 的，所以一直是绿的；
 *    真实环境里 store 的写入走 useEffect，`await refetch()` 解决时
 *    store 还是旧值 → 提示永远不弹。
 *
 *    **单测只能验证你写下的契约，不能验证这个契约本身是否成立。**
 *    那一层要靠 E2E。
 *
 * 📌 vue-v0.11.0 实测：Vue 版**没有**那个时序窗口，
 *    但原因不是 watch 更快，而是引导改成了命令式
 *    （fetchProfileIntoStore 在同一个函数里同步写 store）。
 *    **这条注释保留，因为那个教训与框架无关。**
 */
beforeEach(() => {
  setActivePinia(createPinia())
  resetVersionWatcher()
  useAuthStore().$patch({ perms: ['ticket:ticket:view'], status: 'authenticated' })
  refetchProfile = vi.fn(async () => ({ perms: useAuthStore().perms }))
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

  it('版本号没变时什么都不做', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('1'))
    expect(refetchProfile).not.toHaveBeenCalled()
  })

  it('版本号变了才重拉', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))
    expect(refetchProfile).toHaveBeenCalledTimes(1)
  })

  it('没有版本号头时直接返回', async () => {
    await watchRbacVersion(response())
    expect(refetchProfile).not.toHaveBeenCalled()
  })

  it('resetVersionWatcher 之后重新从「第一次」开始', async () => {
    await watchRbacVersion(response('1'))
    resetVersionWatcher()
    // 不重置的话，下一个用户登录时第一个响应就会被判定为「版本变了」
    await watchRbacVersion(response('2'))
    expect(refetchProfile).not.toHaveBeenCalled()
  })
})

describe('🔴 提示只在**自己的**权限真的变了时才弹', () => {
  it('perms 变了 → 提示', async () => {
    refetchProfile = vi.fn(async () => ({ perms: ['ticket:ticket:view', 'x:y:z'] }))
    configureVersionWatcher({ refetchProfile, notify })
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))
    expect(notify).toHaveBeenCalledWith('你的权限已更新')
  })

  it('🔴 perms 没变 → **不提示**（版本号是全局的，否则大面积误报）', async () => {
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))
    // 任何人改权限，所有在线用户都会走到这里 —— 一律提示对 99% 的人是误报
    expect(notify).not.toHaveBeenCalled()
  })

  it('顺序不同但集合相同 → 不提示（sameSet 是集合比较）', async () => {
    useAuthStore().$patch({ perms: ['a:b:c', 'd:e:f'] })
    refetchProfile = vi.fn(async () => ({ perms: ['d:e:f', 'a:b:c'] }))
    configureVersionWatcher({ refetchProfile, notify })
    await watchRbacVersion(response('1'))
    await watchRbacVersion(response('2'))
    expect(notify).not.toHaveBeenCalled()
  })

  it('refetch 失败（返回 undefined）时不崩、不提示', async () => {
    refetchProfile = vi.fn(async () => undefined)
    configureVersionWatcher({ refetchProfile, notify })
    await watchRbacVersion(response('1'))
    await expect(watchRbacVersion(response('2'))).resolves.toBeUndefined()
    expect(notify).not.toHaveBeenCalled()
  })
})
