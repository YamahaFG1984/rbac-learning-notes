import { useMutation, useQueryClient } from '@tanstack/react-query'

import { resetAuthRedirectGuard } from '@/api/client'

import { loginRequest, logoutRequest } from './api'
import { useAuthStore } from './store'

export function useLogin() {
  const setProfile = useAuthStore((s) => s.setProfile)

  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      loginRequest(username, password),
    onSuccess: (profile) => {
      resetAuthRedirectGuard()
      setProfile(profile)
    },
  })
}

export function useLogout() {
  const reset = useAuthStore((s) => s.reset)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: logoutRequest,
    onSettled: () => {
      // ⚠️ 登出必须清三样，缺一不可：
      //   1. 后端 session（上面的接口）
      //   2. Zustand store —— 否则界面还显示上一个用户
      //   3. Query 缓存   —— 否则**下一个用户会看到上一个用户的数据**
      //
      // 第三条最容易漏，也最严重：这是跨用户数据泄露。
      queryClient.clear()
      reset()
      resetAuthRedirectGuard()
    },
  })
}
