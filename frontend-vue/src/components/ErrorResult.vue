<script setup lang="ts">
import { Button, Result } from 'ant-design-vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

type Kind = '403' | '404' | '500'

const PRESET: Record<Kind, { title: string; subTitle: string }> = {
  '403': {
    title: '403',
    subTitle: '你没有访问此页面的权限。如认为这是配置问题，请联系系统管理员。',
  },
  // ⚠️ 数据权限范围外的记录后端返回 404 而不是 403（后端 ADR-009），
  //    所以文案必须**同时覆盖两种情况且不泄露是哪一种**。
  '404': { title: '404', subTitle: '页面或数据不存在，或你无权访问。' },
  '500': { title: '500', subTitle: '服务器开小差了，请稍后重试。' },
}

/**
 * 🟡 与 React 版的一处形态差异，小但真实。
 *
 *    React：`onRetry?: () => void`——**一个可选回调 prop 同时表达了两件事**，
 *           「要不要显示重试按钮」和「点了做什么」。
 *           `{onRetry && <Button .../>}` 天然成立。
 *
 *    Vue：  事件靠 `defineEmits` 声明，而**声明过的事件会从 `$attrs` 里被摘掉**。
 *           所以 `v-if="$attrs.onRetry"` 恒为 false —— 一个不报错的坑，
 *           表现是「重试按钮永远不出现」。
 *
 *           解法是把两件事拆开：`retryable` 决定显示，`@retry` 决定行为。
 *
 *    → 结论不是谁更好，而是：**「可选回调 prop」这个 React 惯用法在 Vue 里没有直译。**
 *      硬直译会得到一段编译通过、行为错误的代码。
 */
const props = withDefaults(defineProps<{ kind?: Kind; retryable?: boolean }>(), {
  kind: '500',
  retryable: false,
})
defineEmits<{ retry: [] }>()

const preset = computed(() => PRESET[props.kind])
const router = useRouter()
</script>

<template>
  <Result :status="kind" :title="preset.title" :sub-title="preset.subTitle">
    <template #extra>
      <Button v-if="retryable" type="primary" @click="$emit('retry')">重试</Button>
      <Button @click="router.push('/')">返回首页</Button>
    </template>
  </Result>
</template>
