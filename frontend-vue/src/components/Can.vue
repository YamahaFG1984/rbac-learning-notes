<script setup lang="ts">
import { computed } from 'vue'

import { usePermission } from '@/auth/usePermission'
import type { PermCode } from '@/constants/permissions'

/**
 * 按钮级权限。
 *
 * ⚠️⚠️ 这是**体验优化，不是安全边界。**
 *
 *    隐藏了「删除」按钮的用户**照样能删除**——
 *    perms 就在他的浏览器内存里。
 *
 *    🔴 而且 Vue 版**连一个专门的调试口子都不需要**：
 *       Pinia 的 state 本来就是可写的响应式对象，Devtools 里点两下就改了。
 *       React 版为了在 E2E 里表达这件事，还得在构建时挂一个
 *       `window.__AUTH_STORE__`，并写一整段注释解释
 *       「这不是为了测试而降低安全」——**Vue 版连那段解释都不需要**。
 *
 *       两边的实际暴露程度**完全一样**（React DevTools 同样能改组件状态，
 *       攻击者同样可以完全不用你的前端）。Vue 只是更诚实。
 *
 *    > 模板版：攻击者不点你的按钮，他直接发请求。
 *    > SPA 版：他连你的前端都不用。
 *
 *    唯一的安全边界是后端的 `HasPerm` + `ScopedQuerysetMixin`。
 *    **每一个 `<Can>` 都必须有一个对应的后端校验，成对出现，缺一不可。**
 *    vue-v0.14.0 会用 E2E 把这件事钉死：按钮不可见 + 直接发请求得到 403。
 *
 * ⚠️ 内部调用 `usePermission()`，不重新实现判断逻辑。
 *    写两遍的话，将来加语法（比如「否定权限」）要改两处，
 *    而且很可能只改一处。超管的 `['*']` 通配只在 `store.can` 里处理一次。
 *
 * 🟡 与 React 版 `Can.tsx` 的接口对照：
 *      `children`     → 默认 `<slot />`
 *      `fallback` prop → 具名 `<slot name="fallback" />`
 *    其余逐条相同，包括「什么都不传时不渲染」。
 */
const props = defineProps<{
  /** 单个权限码。⚠️ 类型是 PermCode 不是 string —— 写错编译期就报错 */
  perm?: PermCode
  /** 任一满足即可 */
  anyOf?: PermCode[]
  /** 全部满足才行 */
  allOf?: PermCode[]
}>()

const { can } = usePermission()

/*
 * ⚠️ 什么都不传时**不渲染**。
 *
 *    「默认渲染」看起来更宽容，但它会让「写漏了 perm」静默通过——
 *    这正是后端 ADR-002「默认拒绝」在前端的形态：
 *    让默认状态是安全的，写漏立刻可见。
 *
 * ⚠️ 必须是 computed。写成普通常量的话 vue-v0.11.0 权限变更后
 *    按钮不会消失/恢复（V-ADR-009 那一类）。
 */
const ok = computed(() =>
  props.perm
    ? can(props.perm)
    : props.anyOf
      ? props.anyOf.some(can)
      : props.allOf
        ? props.allOf.every(can)
        : false,
)
</script>

<template>
  <slot v-if="ok" />
  <slot v-else name="fallback" />
</template>
