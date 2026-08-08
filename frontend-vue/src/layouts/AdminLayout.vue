<script setup lang="ts">
import { Layout, LayoutContent, Spin } from 'ant-design-vue'

import { useUiStore } from '@/store/uiStore'

import Sidebar from './Sidebar.vue'
import Topbar from './Topbar.vue'

/**
 * ⚠️ 这里**刻意不做任何认证/权限判断**。
 *
 *    拦截统一在 router 的守卫里（vue-v0.2.0 起是最小认证守卫，
 *    vue-v0.5.0 变成完整的 guard.ts）。
 *
 *    在布局组件里再判断一次会造成两处实现，而两处的规则迟早不一致——
 *    这是后端 CLAUDE.md 安全红线第 5 条「权限规则只能有一处实现」
 *    在前端的形态。
 */
const ui = useUiStore()
</script>

<template>
  <Layout style="min-height: 100vh">
    <Sidebar />
    <Layout>
      <Topbar />
      <LayoutContent style="padding: 24px">
        <!--
          ⚠️ vue-v0.5.0 的导航守卫是 async 的（要 await profile），
             慢的时候用户会看到「点了没反应」。先把位置留在这里。

          ⚠️ :delay="200" 不能少 —— 不加的话每次导航都闪一下 spinner，
             比不加还难受。
        -->
        <Spin :spinning="ui.navigating" :delay="200">
          <RouterView />
        </Spin>
      </LayoutContent>
    </Layout>
  </Layout>
</template>
