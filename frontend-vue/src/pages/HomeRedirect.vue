<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import type { MenuNode } from '@/types/auth'

/**
 * 首页：跳到用户有权限的第一个菜单。
 *
 * ⚠️ 不能硬编码跳 `/tickets` —— `no_role` 用户没有任何菜单，
 *    硬跳过去会掉进 403，看起来像系统坏了。
 *
 * 🟡 与 React 版 `HomeRedirect` 的差异：逻辑逐字相同，
 *    只是 `<Navigate to={first} replace />` 换成了 `router.replace(first)`。
 *    这又是「React 用组件表达跳转，Vue 用命令表达跳转」的一个小样本。
 */
const auth = useAuthStore()
const router = useRouter()

const first = computed(() => {
  const walk = (nodes: MenuNode[]): string | null => {
    for (const n of nodes) {
      if (n.routePath) return n.routePath
      const child = walk(n.children)
      if (child) return child
    }
    return null
  }
  return walk(auth.menus)
})

watch(
  first,
  (target) => {
    if (target) void router.replace(target)
  },
  { immediate: true },
)
</script>

<template>
  <div
    v-if="!first"
    style="padding: 48px; text-align: center; color: #8c8c8c"
  >
    你还没有被分配任何菜单权限，请联系系统管理员。
  </div>
</template>
