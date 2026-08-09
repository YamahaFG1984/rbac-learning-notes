<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

/**
 * 渲染期错误的兜底。
 *
 * 🔴 与 React 版的实现差异最大的一个组件，但**限制完全相同**。
 *
 * ─────────────────────────────────────────────────────────────
 * React：必须写 **class 组件**
 *
 *     class AppErrorBoundary extends Component {
 *       static getDerivedStateFromError(error) { return { error } }
 *       componentDidCatch(error, info) { ... }
 *     }
 *
 *   React 到今天也没有 hook 版的 Error Boundary——
 *   这是极少数 hook 覆盖不到的场景，也是 React 里**唯一还必须写 class**
 *   的地方。
 *
 * Vue：`onErrorCaptured` 是普通的 composition 钩子，与其他逻辑写法一致。
 *
 * ─────────────────────────────────────────────────────────────
 * ⚠️⚠️ **但两边的限制一模一样，这才是重点。**
 *
 *   `onErrorCaptured` 和 `componentDidCatch` **都不捕获**：
 *     · 事件处理器里的错误（`@click` / `onClick` 里 throw）
 *     · `setTimeout` / Promise 回调里的错误
 *     · 异步 `queryFn` 的 reject
 *
 *   所以 **5xx 不能靠错误边界兜住**——API 错误走 axios 拦截器那条路
 *   （`errorHandlers.ts`），错误边界管的是**渲染崩溃**。
 *
 *   > 这个限制不是框架的选择，是**「同步渲染栈之外的错误无法被组件捕获」
 *   > 这个事实**。换框架改变不了它。
 *
 * ⚠️ `return false` 不能少：不返回的话错误会继续向上冒泡，
 *    `app.config.errorHandler` 会**重复处理同一个错误**。
 */
const error = ref<unknown | null>(null)

onErrorCaptured((err, _instance, info) => {
  // 生产环境这里接监控。开发环境至少让它出现在控制台里——
  // 被边界兜住的错误默认不会打断执行，很容易被忽略掉。
  console.error('[AppErrorBoundary]', err, info)
  error.value = err
  return false
})

function reset() {
  error.value = null
}

defineExpose({ reset })
</script>

<template>
  <slot v-if="error" name="fallback" :reset="reset" />
  <slot v-else />
</template>
