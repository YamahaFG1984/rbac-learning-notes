<script setup lang="ts">
import { Button, Result } from 'ant-design-vue'

/**
 * 应用级错误的兜底页。
 *
 * ⚠️ 不能复用 `ErrorResult.vue` —— 那个组件用了 `useRouter()`，
 *    而这里可能在路由初始化**之前/之外**（错误可能就发生在那时）。
 *    在路由上下文之外调用 `useRouter()` 会再抛一个错误，
 *    于是错误边界的 fallback 自己也炸了，用户看到彻底的白屏。
 *
 *    **兜底组件的依赖必须比它兜的东西更少。**
 *
 * 🟢 这条约束与 React 版**逐字相同**（那边是 `useNavigate`）——
 *    它讲的是「兜底组件不能依赖可能已经坏掉的上下文」，与框架无关。
 *
 * ⚠️ 所以这里用 `window.location.assign('/')` 而不是 `router.push('/')`：
 *    整页跳转不依赖任何前端状态。
 */
defineEmits<{ retry: [] }>()

// ⚠️ 模板里访问不到全局的 window，要在 script 里包一层。
//    （React 的 JSX 里可以直接写 window.location.assign —— 这是模板
//     「作用域受限」的一个小代价，换来的是模板里不可能出现任意副作用。）
function goHome() {
  window.location.assign('/')
}
</script>

<template>
  <Result
    status="500"
    title="页面出错了"
    sub-title="发生了预期之外的错误。可以重试，若反复出现请联系管理员。"
  >
    <template #extra>
      <Button type="primary" @click="$emit('retry')">重试</Button>
      <Button @click="goHome">返回首页</Button>
    </template>
  </Result>
</template>
