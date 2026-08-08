<script setup lang="ts">
import {
  Alert,
  Button,
  Card,
  Form,
  FormItem,
  Input,
  InputPassword,
  Typography,
  TypographyParagraph,
  TypographyTitle,
} from 'ant-design-vue'
import { computed, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import { useLogin } from '@/auth/useAuth'

/**
 * 校验 redirect 参数，只接受站内路径。
 *
 * `//evil.com` 会被浏览器当成协议相对 URL 跳到外站——
 * 这是后端 v0.7.0 用 url_has_allowed_host_and_scheme 防的
 * **同一个开放重定向问题的前端版本**。
 *
 * ⚠️ 与 React 版逐字相同。它是纯字符串判断，与框架无关。
 */
function safeRedirect(raw: string | null): string {
  if (!raw) return '/'
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/'
  return raw
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const login = useLogin()

const formState = reactive({ username: '', password: '' })

const target = computed(() => {
  const raw = route.query.redirect
  return safeRedirect(typeof raw === 'string' ? raw : null)
})

// 已登录的人打开登录页时直接送走。
// 🟡 React 版这里是 useEffect([status, target, navigate])；
//    Vue 的 watch 不需要依赖数组——它追踪的是回调里实际读到的响应式值。
watch(
  () => auth.status,
  (status) => {
    if (status === 'authenticated') void router.replace(target.value)
  },
  { immediate: true },
)

// ⚠️ 登录失败是 400 不是 401（后端 fe-v0.2.0 刻意如此）。
//    400 不会触发 client.ts 里的「跳登录页」——用户留在本页看错误提示。
const detail = computed(
  () =>
    (login.error.value as { response?: { data?: { detail?: string } } } | null)
      ?.response?.data?.detail ?? null,
)

function onFinish() {
  login.mutate({ username: formState.username, password: formState.password })
}
</script>

<template>
  <div
    style="
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    "
  >
    <Card style="width: 380px">
      <TypographyTitle :level="4" style="text-align: center">
        RBAC 教学系统
      </TypographyTitle>

      <Alert
        v-if="detail"
        type="error"
        show-icon
        :message="detail"
        style="margin-bottom: 16px"
      />

      <Form layout="vertical" :model="formState" autocomplete="off" @finish="onFinish">
        <FormItem
          name="username"
          label="用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        >
          <!-- ⚠️ antdv 的 Input 是 v-model:value 不是 v-model。
               写成 v-model **不报错，输入框就是不响应**。 -->
          <Input v-model:value="formState.username" autofocus size="large" />
        </FormItem>

        <FormItem
          name="password"
          label="密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        >
          <InputPassword v-model:value="formState.password" size="large" />
        </FormItem>

        <Button
          type="primary"
          html-type="submit"
          size="large"
          block
          :loading="login.isPending.value"
        >
          登录
        </Button>
      </Form>

      <TypographyParagraph
        type="secondary"
        style="margin-top: 16px; margin-bottom: 0; font-size: 12px"
      >
        演示账号：superadmin / sysadmin / cs_manager / cs_staff / no_role，
        统一密码 demo1234。
        <br />
        <Typography.Link href="/django/accounts/login/">
          Django 模板版在这里
        </Typography.Link>
      </TypographyParagraph>
    </Card>
  </div>
</template>
