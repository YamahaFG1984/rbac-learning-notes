import { useQuery } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import { fetchProfile } from './api'
import { useAuthStore } from './store'

export const PROFILE_QUERY_KEY = ['profile'] as const

/**
 * 引导阶段拉 profile 失败，且**不是 401**。
 *
 * ⚠️ **401 不是错误**：未登录用户拉 profile 拿到 401 是完全正常的流程，
 *    此时应该让守卫把他送去登录页。只有网络错误 / 5xx 才该显示错误页（VE-2.4）。
 *
 * 🟡 为什么需要这个模块级 ref，而 React 版不需要：
 *
 *    React 的引导在 `<AuthBootstrap>` 组件里，`useProfileQuery()` 的
 *    `error` / `isFetching` 直接就是组件状态，渲染错误页天经地义。
 *
 *    Vue 版从 vue-v0.5.0 起把引导挪进了**导航守卫**（V-ADR-005），
 *    而守卫在组件外——它拿不到、也产生不了组件状态。
 *    要让 App.vue 知道「引导失败了」，只能靠一个共享的响应式变量。
 *
 *    → 又一次同一个模式：**把职责挪出组件树之后，
 *      原本免费的「组件状态」就得自己造一份。**
 */
export const bootError = ref<unknown | null>(null)
export const bootRetrying = ref(false)

/**
 * 拉取当前用户的 profile，并写入权限 store。
 *
 * ⚠️ **这是权限数据的唯一写入口**（F-ADR-005）。
 *    除本文件外，任何地方都不许调 `auth.setProfile()`——
 *    两处写入 = 两个真相源，很快就会不一致。
 *
 *    🔴 这条规则在 Pinia 下**比 Zustand 更难守**：
 *       Pinia 的 state 是公开可写的（`auth.perms = [...]` 完全合法、不报错），
 *       而 Zustand 至少还要走一次 `setState`。
 *       vue-v0.13.0 会加一条结构性测试扫这类直接赋值。
 */
export function useProfileQuery() {
  const auth = useAuthStore()

  const query = useQuery({
    // ⚠️ 即使没有参数也写 computed（V-ADR-009）。
    //    「现在没参数」会变成「以后加了参数」，而加参数的人不会想到
    //    还要改 queryKey 的形式。统一写法把陷阱从「需要记住」变成「不可能踩到」。
    queryKey: computed(() => [...PROFILE_QUERY_KEY]),
    queryFn: fetchProfile,
    // profile 不该被「窗口聚焦」「网络重连」这类事件随意刷新。
    // 它只应由两件事触发重拉：版本号变化（vue-v0.11.0）和收到 403。
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    // 401 重试三次只会让用户多等，跳登录页更慢
    retry: false,
  })

  /*
   * 🟡 对照 React 版的 useEffect：
   *
   *      useEffect(() => {
   *        if (query.data) setProfile(query.data)
   *        else if (query.isError) reset()
   *      }, [query.data, query.isError, setProfile, reset])
   *
   *    Vue 的 watch 不需要依赖数组——它追踪的是回调里实际读到的响应式值。
   *
   *    ⚠️ 但 `immediate: true` 不能少：缓存命中时 data 一开始就有值，
   *       不加的话 watch 不会触发，store 永远是空的。
   *
   *    📌 fe-v0.13.0 在这个位置踩过一个坑（`await refetch()` 之后 store 还没更新，
   *       因为 useEffect 要等重新渲染才跑）。**watch 有没有同样的窗口？**
   *       到 vue-v0.11.0 实测，回填 04 对比文档第 11 节。
   */
  watch(
    [query.data, query.isError],
    ([profile, errored]) => {
      if (profile) auth.setProfile(profile)
      else if (errored) auth.reset()
    },
    { immediate: true },
  )

  return query
}

/**
 * 命令式地拉一次 profile 并写进 store，无论成败都把 status 置为终态。
 *
 * 🔴 **`vue-v0.5.0` 的导航守卫要用它**，所以它必须能在组件外调用——
 *    这就是为什么它不是 composable：`useQuery` 依赖组件实例，
 *    守卫里没有组件实例。
 *
 *    🟡 React 版没有这个函数。它的 profile 拉取只有一条路径
 *    （`<AuthBootstrap>` 里的 `useProfileQuery`），因为它的守卫在组件树里，
 *    天然拿得到 hook。**Vue 的守卫在组件外，所以需要一条命令式的路径。**
 *
 * ⚠️ **无论成功失败都必须把 status 置为终态**（`authenticated` / `anonymous`）。
 *
 *    留在 `unknown` 的话，vue-v0.5.0 的守卫会：
 *      看到 unknown → 拉 profile → 失败 → status 还是 unknown
 *      → `return { ...to }` 重新导航 → 守卫又看到 unknown → **无限循环**
 *      → Vue Router 抛 Maximum recursive navigation guard calls
 */
export async function fetchProfileIntoStore() {
  const auth = useAuthStore()
  try {
    const profile = await fetchProfile()
    auth.setProfile(profile)
    bootError.value = null
    return profile
  } catch (err) {
    auth.reset() // status → 'anonymous'，**不能留在 unknown**
    // ⚠️ 401 不是错误，见 bootError 的注释
    const status = (err as { response?: { status?: number } })?.response?.status
    bootError.value = status === 401 ? null : err
    throw err
  }
}

