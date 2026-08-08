<script setup lang="ts">
/**
 * 根组件。
 *
 * 对照 React 版的 App.tsx：那里有 <BrowserRouter>、<AuthBootstrap>
 * 和两个 Bridge 组件（把「会话过期怎么办」「权限变更怎么办」注入 api 层）。
 *
 * Vue 版这些东西的落点不同：
 *   · 路由：main.ts 里 app.use(router)，不需要包一层组件
 *   · 认证引导：不是组件，是 router.beforeEach（vue-v0.5.0）
 *   · 注入：仍然需要，形状与 React 版相同（vue-v0.11.0 / vue-v0.12.0）
 *
 * 所以 App.vue 会比 App.tsx 薄得多——**不是因为 Vue 更简洁**，
 * 而是因为同样的职责被放到了别的地方。
 */
</script>

<template>
  <RouterView />
</template>
