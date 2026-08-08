<script setup lang="ts">
import { Spin } from 'ant-design-vue'

withDefaults(defineProps<{ tip?: string }>(), { tip: '加载中' })
</script>

<template>
  <div
    style="
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    "
  >
    <!--
      ⚠️ antdv 4 里 Spin 的提示文案是 `tip`。

         React 版（antd 6）用的是 `description`，因为 antd 6 起 `tip` 已废弃——
         **照抄 React 版会写出一个无效属性，不报错、也不显示文案。**

         规律：从 antd 6 往 antdv 4 抄，等于从新版本往旧版本抄。
         React 版注释里写着「XXX 已废弃，用 YYY」的地方，
         Vue 版大概率要用回那个 XXX。遇到就查一次文档，别凭记忆。
    -->
    <Spin size="large" :tip="tip">
      <div style="padding: 24px" />
    </Spin>
  </div>
</template>
