<script setup lang="ts">
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'
import { Button, LayoutHeader, Space, Tag, TypographyText } from 'ant-design-vue'

import { useAuthStore } from '@/auth/store'
import { useLogout } from '@/auth/useAuth'
import { useUiStore } from '@/store/uiStore'

const auth = useAuthStore()
const ui = useUiStore()
const logout = useLogout()
</script>

<template>
  <LayoutHeader
    style="
      background: #fff;
      padding: 0 16px 0 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 56px;
      line-height: 56px;
      border-bottom: 1px solid #f0f0f0;
    "
  >
    <Button type="text" @click="ui.toggleSider()">
      <MenuUnfoldOutlined v-if="ui.siderCollapsed" />
      <MenuFoldOutlined v-else />
    </Button>
    <Space>
      <TypographyText type="secondary">
        {{ auth.user?.department?.name ? `${auth.user.department.name} · ` : ''
        }}{{ auth.user?.realName || auth.user?.username }}
      </TypographyText>
      <Tag v-if="auth.user?.isSuperuser" color="gold">超管</Tag>
      <Button size="small" :loading="logout.isPending.value" @click="logout.mutate()">
        退出登录
      </Button>
    </Space>
  </LayoutHeader>
</template>
