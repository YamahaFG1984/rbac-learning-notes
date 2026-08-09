<script setup lang="ts">
import { App as AntdApp, Button, ConfigProvider, Result, message } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { setUnauthenticatedHandler } from '@/api/client'
import { configureVersionWatcher } from '@/api/versionWatcher'
import { useAuthStore } from '@/auth/store'
import { bootError, fetchProfileIntoStore } from '@/auth/useProfileQuery'

/**
 * ⚠️ vue-v0.5.0 起，**profile 的拉取整个搬进了导航守卫**（V-ADR-005）。
 *
 *    这里不再调 useProfileQuery()——否则 App 的 setup 和守卫会各发一次请求，
 *    首屏两次 profile，直接违反 VNFR-6。
 *
 *    🟡 React 版没有这个取舍：它的引导（<AuthBootstrap>）和守卫（<RequireAuth>）
 *       都在组件树里，共用同一个 useProfileQuery 的缓存，天然只有一次请求。
 *
 *       **把职责挪出组件树的代价，在这里第三次出现**：
 *         · 登出后要自己发起导航（vue-v0.2.0）
 *         · 引导期 401 要自己判断（vue-v0.3.0）
 *         · 引导的错误状态要自己造一个响应式变量（这里）
 */
const auth = useAuthStore()
const router = useRouter()

const retrying = ref(false)

/**
 * 把「权限快照过期了怎么办」注入 axios 拦截器。
 *
 * 和 `setUnauthenticatedHandler` 同一个手法：api 层不认识 Query 和 UI，
 * 由 App 在这里把能力注进去。
 *
 * 🔴📌 **`refetchProfile` 必须走 `fetchProfileIntoStore()`，
 *       不能照抄 React 版的 `queryClient.refetchQueries(['profile'])`。**
 *
 *       vue-v0.5.0 把引导挪进守卫之后，profile **从来没进过 vue-query 的缓存**，
 *       refetchQueries 是**空操作**——照抄 React 的写法完全不工作，且不报错。
 *       实测：getQueryData(['profile']) 返回 undefined，store 也纹丝不动。
 *
 *       这是 V-ADR-005（守卫放导航期）的又一个连锁后果。
 *
 * ⚠️ 仍然**返回拉到的 profile 本身**，不让调用方回头读 store——
 *    那条规则（「异步操作完成」≠「派生状态已更新」）与框架无关，
 *    即使这里 fetchProfileIntoStore 恰好是同步写 store 的。
 *
 * ⚠️ `message` 这里用**静态导入**而不是 `App.useApp()`：
 *    这段代码在 App 组件的 setup 里执行，而 `<AntdApp>` 是它的**子节点**，
 *    此时 useApp 的 context 还没建立。
 *    非阻塞提示不依赖 ConfigProvider 的按钮配置，用静态的没问题。
 */
configureVersionWatcher({
  refetchProfile: async () => {
    try {
      return await fetchProfileIntoStore()
    } catch {
      return undefined
    }
  },
  // ⚠️ 非阻塞提示，不是 Modal —— 这不是需要用户确认的事。
  //    但也不能什么都不说：按钮突然消失、菜单少一项，
  //    用户会以为自己看错了或者系统抽风。
  notify: (text) => message.info(text),
})

/** VE-2.4：引导失败时的重试。重新拉一次 profile，成功就补注册路由并重新导航。 */
async function retryBoot() {
  retrying.value = true
  try {
    // ⚠️ 不需要手动注册路由——setProfile 写 menus 时 sync watcher 会做（dynamic.ts）
    await fetchProfileIntoStore()
    await router.replace(router.currentRoute.value.fullPath)
  } catch {
    // bootError 已由 fetchProfileIntoStore 设置，模板会显示
  } finally {
    retrying.value = false
  }
}

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
   *    实测踩到的真 bug（vue-v0.3.0 发现，从 vue-v0.2.0 起就存在）：
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
   *       Vue 的注入发生在 **setup** 时，没有这道门。
   *
   *       → **React 的行为由组件树的形状决定，Vue 的行为由代码的执行顺序决定。**
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
       表现是「配了但没生效」，比完全没配更难查。实测确认。
  -->
  <ConfigProvider :locale="zhCN" :auto-insert-space-in-button="false">
    <!--
      🔴📌 `<App>` 不是可选的装饰，它解决一个实测踩到的真问题。

         `Modal.confirm()` / `message.*` 这类**静态方法**是在应用组件树
         **之外**渲染的（挂到 body 上的独立 vnode 树），
         因此**拿不到 `<ConfigProvider>` 的配置**。

         实测：树内的按钮是「删除」「派单」（正确），
         而 `Modal.confirm()` 的按钮渲染成 **「取 消」「确 定」**——
         `auto-insert-space-in-button="false"` 对它完全无效。

         后果：所有按文本找确认框按钮的代码（含 E2E）全部失效，
         而报错只说「找不到元素」。

         `<App>` 提供了 context 感知的 `modal` / `message` / `notification`，
         调用方改用 `App.useApp()` 拿到的那份即可。

         🟢 **React 版早就这么做了**（main.tsx 里的 `<AntdApp>` +
            页面里的 `App.useApp()`）——antd 5 引入 `<App>` 正是为了这个。
            我一开始直接 import 了静态的 `Modal`，是**没照抄到位**，
            不是框架差异。
    -->
    <AntdApp>
    <!--
      VE-2.4：profile 拉不到时给可重试的错误页，而不是白屏。
      ⚠️ 401 不排在这里——那是「你没登录」，是正常流程，由守卫送去登录页。
    -->
    <Result
      v-if="bootError"
      status="warning"
      title="无法加载你的权限信息"
      sub-title="请检查网络后重试。在权限信息加载成功之前，系统不会展示任何业务界面。"
    >
      <template #extra>
        <Button type="primary" :loading="retrying" @click="retryBoot">重试</Button>
      </template>
    </Result>

    <!--
      VE-2.3 现在由**守卫**保证：status === 'unknown' 时守卫会 await profile，
      导航根本不会完成，业务页面不会被创建。

      这里保留 v-else 只是为了在引导失败时不同时渲染两套 UI。
    -->
    <RouterView v-else />
    </AntdApp>
  </ConfigProvider>
</template>
