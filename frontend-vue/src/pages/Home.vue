<script setup lang="ts">
import {
  Button,
  Card,
  Descriptions,
  DescriptionsItem,
  Space,
  TypographyParagraph,
  TypographyTitle,
} from 'ant-design-vue'

import { useAuthStore } from '@/auth/store'
import { useLogout } from '@/auth/useAuth'
import FullPageSpin from '@/components/FullPageSpin.vue'

/**
 * vue-v0.2.0 的临时首页。真正的后台布局在 vue-v0.3.0。
 *
 * 它存在的意义是**验收 F-ADR-002**：把 document.cookie 打在页面上，
 * 让「看得到 csrftoken、看不到 sessionid」这件事变成肉眼可见的。
 */
const auth = useAuthStore()
const logout = useLogout()

// ⚠️ document.cookie 不是响应式的，读一次就行——
//    它只是给人看的验收展示，不需要跟着变。
const cookies = document.cookie
</script>

<template>
  <!-- 「还没问过后端」≠「确定未登录」。unknown 时不渲染业务内容，
       否则会闪一下「未登录」的界面再跳回来。 -->
  <FullPageSpin v-if="auth.status === 'unknown'" />

  <div v-else style="max-width: 720px; margin: 64px auto; padding: 24px">
    <Space style="width: 100%; justify-content: space-between; margin-bottom: 16px">
      <TypographyTitle :level="3" style="margin: 0">已登录</TypographyTitle>
      <Button :loading="logout.isPending.value" @click="logout.mutate()">
        退出登录
      </Button>
    </Space>

    <Card title="当前会话">
      <Descriptions :column="1" size="small">
        <DescriptionsItem label="用户">
          {{ auth.user?.realName || auth.user?.username }}
        </DescriptionsItem>
        <DescriptionsItem label="部门">
          {{ auth.user?.department?.name ?? '—' }}
        </DescriptionsItem>
        <DescriptionsItem label="超管">
          {{ auth.user?.isSuperuser ? '是' : '否' }}
        </DescriptionsItem>
        <DescriptionsItem label="权限码数">{{ auth.perms.length }}</DescriptionsItem>
        <DescriptionsItem label="document.cookie">
          <code style="font-size: 12px">{{ cookies || '（空）' }}</code>
        </DescriptionsItem>
      </Descriptions>
      <TypographyParagraph type="secondary" style="font-size: 12px; margin-top: 8px">
        ⬆️ 上面这行是 F-ADR-002 的验收：看得到 csrftoken，
        <strong>看不到 sessionid</strong>——真正的凭证是 httpOnly 的。
      </TypographyParagraph>
    </Card>
  </div>
</template>
