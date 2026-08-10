import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import {
  clearDynamicRoutes,
  dynamicRouteCount,
  installDynamicRoutes,
} from '@/router/dynamic'
import { CS_MANAGER_PROFILE, SUPERADMIN_PROFILE } from '@/test/fixtures'

/**
 * 🔴🔴 **本文件在 React 版里不存在** —— 它测的是 V-ADR-004 的那笔债。
 *
 * React 的路由表是 `f(menus)`（重建），旧路由自动消失，无从测起。
 * Vue 的 `addRoute()` 是增量的，注册与清理都是**需要被执行的动作**，
 * 所以必须有测试钉住它们。
 *
 * ⚠️ 尤其是清理：不测的话，「换账号后残留」只有 E2E 能发现，
 *    而那个 bug **只在「第二次」才暴露**（第二次登录、第二个账号）。
 */
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: { template: '<div/>' } },
      {
        path: '/', name: 'layout', component: { template: '<div><RouterView/></div>' },
        children: [{ path: '403', component: { template: '<div/>' } }],
      },
    ],
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  clearDynamicRoutes()
})

describe('动态路由：注册是 menus 的派生效果', () => {
  it('🔴 setProfile 写 menus 时**自动**注册（不需要显式调用）', () => {
    const router = makeRouter()
    installDynamicRoutes(router)
    expect(dynamicRouteCount()).toBe(0)

    /*
     * 🔴 第一版把注册写成守卫里的一个步骤，结果**登录**时 status 从
     *    anonymous 直跳 authenticated，不经过那个分支 → 路由没注册 →
     *    「登录成功却被自己的前端 403」。
     *
     *    修法不是补第二个调用点，是把它变回派生值。这条测试钉的就是这个。
     */
    useAuthStore().setProfile(SUPERADMIN_PROFILE)
    expect(dynamicRouteCount()).toBeGreaterThan(0)
    expect(router.getRoutes().some((r) => r.path === '/system/users')).toBe(true)
  })

  it('🔴 reset（登出）时自动清理 —— 不需要在登出里手动调', () => {
    const router = makeRouter()
    installDynamicRoutes(router)
    useAuthStore().setProfile(SUPERADMIN_PROFILE)
    expect(router.getRoutes().some((r) => r.path === '/system/users')).toBe(true)

    useAuthStore().reset()
    expect(dynamicRouteCount()).toBe(0)
    expect(router.getRoutes().some((r) => r.path === '/system/users')).toBe(false)
  })

  it('🔴🔴 换账号不残留上一个账号的路由（VE-3.8 / VUS-6）', () => {
    const router = makeRouter()
    installDynamicRoutes(router)
    const auth = useAuthStore()

    auth.setProfile(SUPERADMIN_PROFILE)
    auth.reset()
    auth.setProfile(CS_MANAGER_PROFILE)

    expect(router.getRoutes().some((r) => r.path === '/system/users')).toBe(false)
    expect(router.getRoutes().some((r) => r.path === '/tickets')).toBe(true)
  })

  it('🔴 重复注册不叠加（先清再加）', () => {
    const router = makeRouter()
    installDynamicRoutes(router)
    const auth = useAuthStore()

    auth.setProfile(CS_MANAGER_PROFILE)
    const first = dynamicRouteCount()
    auth.setProfile(CS_MANAGER_PROFILE)

    // 不「先清再加」的话 registered 数组会无限增长，
    // 而且同名路径被注册两次（vue-v0.5.0 实测见过 /tickets 出现两次）
    expect(dynamicRouteCount()).toBe(first)
    expect(router.getRoutes().filter((r) => r.path === '/tickets')).toHaveLength(1)
  })
})
