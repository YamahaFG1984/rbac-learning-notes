import { VueQueryPlugin } from '@tanstack/vue-query'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { resetAuthRedirectGuard } from '@/api/client'
import { useAuthStore } from '@/auth/store'
import { useLogin, useLogout } from '@/auth/useAuth'
import { setCurrentUser } from '@/test/msw/handlers'

/**
 * `useLogin` / `useLogout` 依赖组件上下文（`useMutation` + `useRouter`），
 * 所以只能挂载一个宿主组件来测——这也是它们与 `fetchProfileIntoStore`
 * （命令式、组件外可用）分工的原因。
 */
function mountWith(setup: () => Record<string, unknown>) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/login', component: { template: '<div/>' } },
    ],
  })
  const Host = defineComponent({ setup, render: () => h('div') })
  const wrapper = mount(Host, {
    global: { plugins: [router, VueQueryPlugin] },
  })
  return { wrapper, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
  resetAuthRedirectGuard()
})

describe('useLogin', () => {
  it('成功后把 profile 写进 store', async () => {
    let login!: ReturnType<typeof useLogin>
    mountWith(() => {
      login = useLogin()
      return {}
    })
    login.mutate({ username: 'cs_manager', password: 'demo1234' })
    await vi.waitFor(() => expect(useAuthStore().status).toBe('authenticated'))
    expect(useAuthStore().perms).toContain('ticket:ticket:delete')
  })

  it('密码错误时不写 store', async () => {
    let login!: ReturnType<typeof useLogin>
    mountWith(() => {
      login = useLogin()
      return {}
    })
    login.mutate({ username: 'cs_manager', password: 'wrong' })
    await vi.waitFor(() => expect(login.isError.value).toBe(true))
    expect(useAuthStore().status).toBe('unknown')
  })
})

describe('useLogout', () => {
  it('🔴 清 store + 清 Query 缓存 + **显式跳转登录页**', async () => {
    setCurrentUser('cs_manager')
    let logout!: ReturnType<typeof useLogout>
    const { router } = mountWith(() => {
      logout = useLogout()
      return {}
    })
    await router.push('/')
    useAuthStore().setProfile({
      user: { id: 1, username: 'x', realName: 'x', department: null, isSuperuser: false },
      perms: ['a:b:c'], menus: [], knownRoutes: [],
    })

    logout.mutate()
    await vi.waitFor(() => expect(useAuthStore().status).toBe('anonymous'))
    await flushPromises()

    /*
     * 🔴 这一行是 vue-v0.2.0 实测逼出来的，React 版**不需要**：
     *
     *    React 的守卫是**组件**（RequireAuth），status 一变就重新渲染、
     *    <Navigate> 自动生效；Vue 的守卫是**导航流程的一环**，
     *    auth.reset() 不触发任何导航，守卫根本不会运行。
     *
     *    > React 的守卫是「状态的函数」，Vue 的守卫是「导航的钩子」。
     */
    expect(router.currentRoute.value.path).toBe('/login')
    expect(useAuthStore().perms).toEqual([])
  })
})
