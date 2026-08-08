<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { ConfigProvider } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { fetchProfile } from '@/auth/api'
import { useAuthStore } from '@/auth/store'

/**
 * 应用启动时问一次后端「我登录了吗」。
 *
 * 前端不保存 token——它靠这一次请求判断认证状态（F-ADR-002/003）。
 * vue-v0.4.0 会把它换成正式的 useProfileQuery 并接进权限判断，
 * vue-v0.5.0 再把触发时机挪到导航守卫里。
 */
const auth = useAuthStore()
const router = useRouter()

const { data, isError } = useQuery({
  // ⚠️ 即使没有参数也写 computed（V-ADR-009）。
  //    「现在没参数」会变成「以后加了参数」，而加参数的人不会想到
  //    还要改 queryKey 的形式。统一写法把陷阱从「需要记住」变成「不可能踩到」。
  queryKey: computed(() => ['profile']),
  queryFn: fetchProfile,
  retry: false,
  staleTime: Infinity,
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
 *    ⚠️ 但 immediate: true 不能少：缓存命中时 data 一开始就有值，
 *       不加的话 watch 不会触发，store 永远是空的。
 *
 *    📌 fe-v0.13.0 在这个位置踩过一个坑（await refetch() 之后 store 还没更新，
 *       因为 useEffect 要等重新渲染才跑）。**watch 有没有同样的窗口？**
 *       到 vue-v0.11.0 实测，回填 04 对比文档第 11 节。
 */
watch(
  [data, isError],
  ([profile, errored]) => {
    if (profile) auth.setProfile(profile)
    else if (errored) auth.reset()
  },
  { immediate: true },
)

/**
 * 把「会话过期怎么办」注入 axios 拦截器——避免 api 层直接依赖路由。
 *
 * ⚠️ 形状与 React 版的 UnauthenticatedBridge **完全相同**。
 *    React 用注入的理由是依赖方向；Vue 版**多一条**：
 *    api/client.ts 在 main.ts 里被 import，那时 pinia/router 都还没就绪
 *    （V-ADR-003）。同一个做法，两边理由不同。
 */
setUnauthenticatedHandler(() => {
  auth.reset()
  const here = window.location.pathname + window.location.search
  void router.replace({ path: '/login', query: { redirect: here } })
})
</script>

<template>
  <!--
    ⚠️ auto-insert-space-in-button 必须显式关掉。

       不关的话 antdv 会给「登录」这类两个汉字的按钮自动插入空格，
       渲染成「登 录」。后果是任何按文本查找按钮的代码都失效——
       测试里按 name: '登录' 找不到元素，而报错只说「找不到」，
       完全指不到真正原因。

       🔴 注意它和 React 版的写法**不一样**：
          antd 6（React）：<ConfigProvider button={{ autoInsertSpace: false }}>
          antdv 4（Vue） ：:auto-insert-space-in-button="false"

       **照抄 React 版在 antdv 里是个无效属性，不报错也不生效**——
       表现是「配了但没生效」，比完全没配更难查，因为你会认为「我明明配了」。
       这是 04 对比文档「还没验证的三件事」第 2 条的现场，实测确认。
  -->
  <ConfigProvider :locale="zhCN" :auto-insert-space-in-button="false">
    <RouterView />
  </ConfigProvider>
</template>
