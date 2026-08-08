<script setup lang="ts">
import {
  AppstoreOutlined,
  BarChartOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import { LayoutSider, Menu, type MenuProps } from 'ant-design-vue'
import { computed, h, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUiStore } from '@/store/uiStore'

/**
 * ⚠️⚠️ vue-v0.3.0：菜单**硬编码**，没有任何权限判断。
 *
 *    vue-v0.6.0 会整个删掉这个常量，改为由 profile 的 menus 渲染。
 *    保持结构简单，让那次改动的 diff 只讲「动态化」这一件事——
 *    和后端 v0.8.0 → v0.11.0、React fe-v0.4.0 → fe-v0.8.0 是同一个手法，
 *    这已经是**第三次**使用它了。
 *
 *    在此之前，所有登录用户都能看到全部菜单，包括他点进去会 403 的。
 *    **这个难看的状态是刻意的**：它让你直观感受到为什么要做动态菜单。
 *
 *    → 用 cs_staff 登录看一眼「用户管理」还在那儿，记住这个画面。
 */
const STATIC_ITEMS: MenuProps['items'] = [
  {
    key: 'ticket',
    icon: () => h(FileTextOutlined),
    label: '工单管理',
    children: [{ key: '/tickets', label: '工单列表' }],
  },
  {
    key: 'system',
    icon: () => h(SettingOutlined),
    label: '系统管理',
    children: [
      { key: '/system/depts', label: '部门管理' },
      { key: '/system/users', label: '用户管理' },
      { key: '/system/roles', label: '角色管理' },
      { key: '/system/perms', label: '权限点' },
    ],
  },
  {
    key: 'monitor',
    icon: () => h(BarChartOutlined),
    label: '系统监控',
    children: [{ key: '/monitor/audit', label: '审计日志' }],
  },
]

const ui = useUiStore()
const route = useRoute()
const router = useRouter()

// 🟡 与 React 版的一处差异：
//    React 要 `const { pathname } = useLocation()` 才能订阅路由变化；
//    Vue 的 useRoute() 返回的就是响应式对象，computed 自动追踪。
const selectedKeys = computed(() => [route.path])

/*
 * 🔴 **antdv 的 Menu 没有 `defaultOpenKeys`**，只有 `openKeys`。
 *
 *    React（antd 6）写的是 `defaultOpenKeys={['ticket','system','monitor']}`。
 *    照抄成 `:default-open-keys="[...]"` 在 antdv 里是个**未声明的 prop**——
 *    它会掉进 $attrs 落到根元素上，**不报错、不警告、也不生效**。
 *
 *    表现：所有子菜单默认收起，"部门管理" 在 DOM 里但不可见。
 *    这个 bug 是 E2E 点不到菜单才暴露的，肉眼扫一眼页面很容易以为「设计如此」。
 *
 *    这已经是本阶段第 **4** 次「照抄 React 版写出无效属性」：
 *      vue-v0.2.0  ConfigProvider 的 autoInsertSpace
 *      vue-v0.2.0  Spin 的 tip / description
 *      vue-v0.3.0  Modal 的 destroyOnClose（vue-v0.10.0 会遇到）
 *      vue-v0.3.0  Menu 的 defaultOpenKeys ← 这里
 *
 *    ⚠️ 前三次都是「同一个能力换了名字」，**这一次是能力压根不存在**——
 *       antdv 只提供受控的 openKeys，非受控的默认值要自己给初始值。
 *
 *    📌 共同点：**Vue 的模板对未知属性是宽容的**（透传到 $attrs），
 *       而 React 的 TSX 对未知 prop 会**编译期报错**。
 *       这是 JSX 相对模板在这一点上的实打实优势，
 *       与「Vue vs React 谁更好」无关——它只是类型检查边界的位置不同。
 */
const openKeys = ref<string[]>(['ticket', 'system', 'monitor'])
</script>

<template>
  <LayoutSider :collapsed="ui.siderCollapsed" theme="dark" :width="220">
    <div
      style="
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-weight: 600;
        letter-spacing: 1px;
      "
    >
      <AppstoreOutlined v-if="ui.siderCollapsed" />
      <template v-else>RBAC 教学系统</template>
    </div>
    <Menu
      theme="dark"
      mode="inline"
      :selected-keys="selectedKeys"
      v-model:open-keys="openKeys"
      :items="STATIC_ITEMS"
      @click="({ key }) => router.push(String(key))"
    />
  </LayoutSider>
</template>
