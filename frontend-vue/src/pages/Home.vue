<script setup lang="ts">
import { Alert, Button, Card, Space, Typography } from 'ant-design-vue'
import { ref } from 'vue'

import { client } from '@/api/client'

/**
 * vue-v0.1.0 的占位页，只用来验证一件事：**同域代理通了。**
 *
 * 它调 /api/v1/health/ ——浏览器发的是 http://localhost:5174/api/v1/health/，
 * Vite 转发到 http://127.0.0.1:8000/api/v1/health/。
 * 全程单一源，所以浏览器会自动带 Cookie，也完全不需要 CORS（F-ADR-002）。
 *
 * ⚠️ 注意顶部的 import：组件是**按需引入**的，不是靠 app.use(Antd) 全局注册。
 *    理由见 main.ts 里那段长注释——全局注册会让 tree-shaking 失效，
 *    实测一个占位页就 1.53 MB，比 React 版整个应用还大。
 *
 *    <script setup> 里 import 进来的组件在模板里直接可用，不需要 components 选项。
 *    这一点和 React 的 `import { Button } from 'antd'` 完全同构。
 */
const result = ref<string>('未请求')
const loading = ref(false)

async function ping() {
  loading.value = true
  try {
    const res = await client.get('/health/')
    result.value = `OK — ${JSON.stringify(res.data)}`
  } catch (err) {
    result.value = `失败 — ${(err as Error).message}`
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="padding: 48px; max-width: 720px; margin: 0 auto">
    <h1>RBAC 教学系统 · Vue 3</h1>
    <p style="color: #8c8c8c">
      阶段四（<code>feat/vue-frontend</code>）。同一个权限内核的第四种表现层。
    </p>

    <Card title="同域代理自检" style="margin-top: 24px">
      <Space direction="vertical" style="width: 100%">
        <Button type="primary" :loading="loading" @click="ping">
          请求 /api/v1/health/
        </Button>
        <Typography.Text code>{{ result }}</Typography.Text>
      </Space>
    </Card>

    <Alert
      style="margin-top: 24px"
      type="info"
      show-icon
      message="只访问 :5174"
      description="不要直接开 :8000 的页面。同域是 httpOnly Cookie 方案的硬性前提，Vite 的代理把 /api 转给 Django，全程单一源、不需要 CORS。"
    />
  </div>
</template>
