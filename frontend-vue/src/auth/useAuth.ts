import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'

import { resetAuthRedirectGuard } from '@/api/client'
import { resetVersionWatcher } from '@/api/versionWatcher'

import { loginRequest, logoutRequest } from './api'
import { useAuthStore } from './store'

/**
 * ⚠️ `useMutation` 的 `onSuccess` / `onSettled` 在 v5 里**仍然存在**——
 *    被移除的是 `useQuery` 的 `onSuccess`（React 版 useProfileQuery 的注释里记过）。
 *    两个适配层在这一点上完全一致。
 */
export function useLogin() {
  const auth = useAuthStore()

  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      loginRequest(username, password),
    onSuccess: (profile) => {
      resetAuthRedirectGuard()
      auth.setProfile(profile)
    },
  })
}

export function useLogout() {
  const auth = useAuthStore()
  const queryClient = useQueryClient()
  const router = useRouter()

  return useMutation({
    mutationFn: logoutRequest,
    onSettled: async () => {
      // ⚠️ 登出必须清三样，缺一不可：
      //   1. 后端 session（上面的接口）
      //   2. Pinia store   —— 否则界面还显示上一个用户
      //   3. Query 缓存    —— 否则**下一个用户会看到上一个用户的数据**
      //
      // 第三条最容易漏，也最严重：这是跨用户数据泄露。
      //
      // 📌 **原本以为这里要加第四样 clearDynamicRoutes()，实测发现不用。**
      //
      //    vue-v0.5.0 把「注册动态路由」做成了 auth.menus 的**派生效果**
      //    （router/dynamic.ts 的 sync watcher）。auth.reset() 把 menus 清空，
      //    watcher 立刻把路由移除——**和 React 版重建 router 的效果一样**。
      //
      //    > 「增量 API 多欠一笔债」是真的，但**债可以一次性还清**：
      //    > 把命令式的 addRoute 包装成派生效果，就拿回了 React 的那个性质。
      //    > 代价是你必须自己想到这一步——框架不会提示你。
      //
      queryClient.clear()
      auth.reset()
      resetAuthRedirectGuard()
      /*
       * ⚠️ 不重置的话，下一个用户登录时 lastSeen 还是上一个会话的值，
       *    第一个响应就会被判定为「版本变了」，白白多拉一次 profile。
       */
      resetVersionWatcher()

      /*
       * 🔴🔴 **必须显式跳转。这一行 React 版没有，而漏掉它是个真 bug。**
       *
       *    实测（vue-v0.2.0 浏览器验证）：不加这一行，登出后
       *    session 清了、store 清了、cookie 也没了，
       *    但**用户仍然停在原页面上**，界面显示的还是登录态的壳。
       *
       *    根因是 V-ADR-005 的另一面：
       *
       *      React 的守卫是**组件**（RequireAuth）——它在渲染树里，
       *        status 一变就重新渲染，<Navigate> 自动生效。
       *      Vue 的守卫是**导航流程的一环**（beforeEach）——
       *        `auth.reset()` 不触发任何导航，守卫**根本不会运行**。
       *
       *    我在 V-ADR-005 里写了导航期守卫的好处（拦得更早、组件不创建、
       *    请求不发出），**没写这个代价**：
       *
       *        导航期守卫只对「导航」生效，对「状态变化」无感。
       *        凡是「状态变了所以该换页面」的场景，都必须自己发起导航。
       *
       *    ⚠️ 这也解释了为什么 api/client.ts 的 401 处理必须注入一个
       *       跳转回调而不能只清 store —— 同一个原因。
       */
      await router.replace('/login')
    },
  })
}
