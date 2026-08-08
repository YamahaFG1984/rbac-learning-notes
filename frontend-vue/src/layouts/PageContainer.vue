<script setup lang="ts">
import { Space, TypographyTitle } from 'ant-design-vue'

/**
 * 页面外壳：标题 + 右侧操作区 + 内容。
 *
 * 对应模板版的 {% block page_title %} / {% block page_actions %} / {% block content %}。
 *
 * 📌 三种表现层，三种复用手法：
 *      Django 模板 → **继承**（{% extends %} + block）
 *      React       → **组合**（children + extra prop）
 *      Vue         → **插槽**（默认 slot + 具名 slot）
 *
 *    插槽和 React 的 children/prop 是同一件事的两种语法；
 *    模板继承是另一种思路（子模板填父模板的坑，而不是父组件接收子内容）。
 */
defineProps<{ title: string }>()
</script>

<template>
  <div
    style="
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    "
  >
    <TypographyTitle :level="4" style="margin: 0">{{ title }}</TypographyTitle>
    <Space><slot name="extra" /></Space>
  </div>
  <slot />
</template>
