<script setup lang="ts">
import { Button, ConfigProvider, Result } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { useAuthStore } from '@/auth/store'
import { useProfileQuery } from '@/auth/useProfileQuery'
import FullPageSpin from '@/components/FullPageSpin.vue'

/**
 * 应用启动时问一次后端「我登录了吗」。
 *
 * 前端不保存 token——它靠这一次请求判断认证状态（F-ADR-002/003）。
 *
 * ⚠️ vue-v0.5.0 会把触发时机整个挪到导航守卫里
 *    （那时才需要「profile 到手后再 addRoute」的时序）。
 */
const auth = useAuthStore()
const router = useRouter()

const { error, isError, isFetching, refetch } = useProfileQuery()

/*
 * ⚠️ **401 不是错误。**
 *
 *    未登录用户拉 profile 拿到 401 是完全正常的流程——此时应该正常渲染，
 *    让路由守卫把他送去登录页。只有网络错误 / 5xx 才该显示错误页（VE-2.4）。
 *
 *    🟡 React 版这段逻辑在 <AuthBootstrap> 组件里，Vue 版直接放在 App 的
 *       setup + template 里。**判断逻辑逐字相同，只是落点不同**——
 *       React 需要一个组件来「包住 children 并决定渲不渲染」，
 *       Vue 用 v-if 就够了。
 */
const httpStatus = computed(
  () => (error.value as { response?: { status?: number } } | null)?.response?.status,
)
const bootFailed = computed(() => isError.value && httpStatus.value !== 401)

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

  /*
   * 🔴 **已经在登录页时，不要把自己记成 redirect 目标。**
   *
   *    实测踩到的真 bug（vue-v0.3.0 发现，但从 vue-v0.2.0 起就存在，
   *    只是被当时测试的导航顺序掩盖了）：
   *
   *      直接打开 /login → 引导阶段拉 profile 拿到 401
   *        → 这个 handler 把 URL 改成 /login?redirect=/login
   *        → 登录成功 → target = safeRedirect('/login') = '/login'
   *        → **跳回登录页**，表现是「登录按钮点了没反应」
   *
   *    📌 **React 版没有这个 bug，但原因是结构性的，不是它写了这个判断。**
   *
   *       React 的 <UnauthenticatedBridge /> 是 <AuthBootstrap> 的**子节点**，
   *       而 AuthBootstrap 在 status === 'unknown' 时只渲染 spinner、
   *       **不渲染 children** —— 所以引导阶段那个 401 到达时，
   *       setUnauthenticatedHandler **根本还没被调用**。
   *
   *       它的「注入」发生在**组件挂载**时，天然带着一道时序门；
   *       Vue 的注入发生在 **setup** 时（App 的 setup 一开始就跑完），
   *       没有这道门。
   *
   *       → 同一段逻辑，React 靠组件树层级顺带获得了保护，Vue 必须显式写出来。
   *         这和「导航期守卫对状态变化无感」是同一类差异的两面：
   *         **React 的行为由组件树的形状决定，Vue 的行为由代码的执行顺序决定。**
   */
  if (window.location.pathname === '/login') {
    void router.replace('/login')
    return
  }

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
    <!-- VE-2.4：profile 拉不到时给可重试的错误页，而不是白屏 -->
    <Result
      v-if="bootFailed"
      status="warning"
      title="无法加载你的权限信息"
      sub-title="请检查网络后重试。在权限信息加载成功之前，系统不会展示任何业务界面。"
    >
      <template #extra>
        <Button type="primary" :loading="isFetching" @click="refetch()">重试</Button>
      </template>
    </Result>

    <!--
      VE-2.3：「还没问过后端」≠「确定未登录」。

      这是「让默认状态是安全的」在前端的形态：**未知 ≠ 允许**。
      看似「初始 perms 是空数组，恰好等价于无权限，先渲染也没事」——
      这个侥幸才最危险：只要有人写出
          perms.length === 0 ? 显示全部 : 按权限显示
      （理由是「还没加载完就先都显示吧」），就会真的闪现越权内容。
      干脆不渲染，就不存在这个口子。

      ⚠️ vue-v0.5.0 起这一层会**同时**由导航守卫兜住（守卫里 await profile）。
         两道并存不是重复：守卫管的是「导航」，这里管的是「首次挂载」。
    -->
    <FullPageSpin v-else-if="auth.status === 'unknown'" tip="正在加载权限信息" />

    <RouterView v-else />
  </ConfigProvider>
</template>
