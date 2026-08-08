<script setup lang="ts">
import { useRoute } from 'vue-router'

/**
 * 后端 `component` 字段配错时的降级页面。
 *
 * ⚠️ 关键是**只坏这一个页面**，其余页面照常——
 *    一个配错的字符串不该让整个应用白屏。
 */
const route = useRoute()
</script>

<template>
  <div style="padding: 24px; color: #cf1322">
    页面组件未找到：<code>{{ route.meta.component }}</code>
    <div style="color: #8c8c8c; margin-top: 8px; font-size: 12px">
      后端权限点的 component 字段配置有误。用
      <code>python manage.py sync_permissions --check-frontend</code> 排查。
    </div>
  </div>
</template>
