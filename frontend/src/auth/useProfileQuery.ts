import { useEffect } from 'react'

import { useQuery } from '@tanstack/react-query'

import { fetchProfile } from './api'
import { useAuthStore } from './store'

export const PROFILE_QUERY_KEY = ['profile'] as const

/**
 * 拉取当前用户的 profile，并写入权限 store。
 *
 * ⚠️ **这是权限数据的唯一写入口**（F-ADR-005）。
 *    除本文件外，任何地方都不许调 useAuthStore.setProfile()——
 *    两处写入 = 两个真相源，很快就会不一致。
 *
 * ⚠️ TanStack Query v5 **移除了 useQuery 的 onSuccess 回调**
 *    （只有 useMutation 还有）。所以「拉到后写 store」只能用 useEffect。
 *    规格书提示 1 里写的 `useProfileQuery({ onSuccess })` 是 v4 的写法，
 *    v5 下不生效——而且它不报错，是静默失效。
 */
export function useProfileQuery() {
  const setProfile = useAuthStore((s) => s.setProfile)
  const reset = useAuthStore((s) => s.reset)

  const query = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: fetchProfile,
    // profile 不该被「窗口聚焦」「网络重连」这类事件随意刷新。
    // 它只应由两件事触发重拉：版本号变化（fe-v0.13.0）和收到 403。
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    // 401 重试三次只会让用户多等，跳登录页更慢
    retry: false,
  })

  useEffect(() => {
    if (query.data) setProfile(query.data)
    else if (query.isError) reset()
  }, [query.data, query.isError, setProfile, reset])

  return query
}
