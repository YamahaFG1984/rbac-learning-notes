<script setup lang="ts">
import { AppstoreOutlined } from '@ant-design/icons-vue'
import { LayoutSider, Menu } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/auth/store'
import { useUiStore } from '@/store/uiStore'

import { findActiveKeys, toMenuItems } from './menuAdapter'

const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

/*
 * ⚠️ 必须是 `computed`。
 *
 *    写成 `const items = toMenuItems(auth.menus)` 在**本 tag 看不出问题**
 *    （menus 拉回来一次就不变了），但 vue-v0.11.0 的权限变更感知一上，
 *    菜单就**永远不更新**了。
 *
 *    🟡 React 版这里是 `useMemo(..., [menus])`——它的默认行为是「每次重算」，
 *       useMemo 只是**阻止**重算；Vue 的默认行为是「不重算」，
 *       computed 是**启用**重算。**忘了写的后果方向相反：
 *       React 是性能问题，Vue 是正确性问题。**
 */
const items = computed(() => toMenuItems(auth.menus))

// 🟡 React 要 `const { pathname } = useLocation()` 才能订阅路由变化；
//    Vue 的 useRoute() 返回的就是响应式对象，computed 自动追踪。
const active = computed(() => findActiveKeys(auth.menus, route.path))

/**
 * openKeys 受控，但只在**路径变化**时**并入**新的展开项。
 *
 * ⚠️ 如果直接 `openKeys.value = active.value.openKeys`（覆盖），
 *    用户手动展开的其它目录会在下一次导航时被抹掉，
 *    手动折叠的也会被展开回去——看起来像「折叠按钮坏了」。
 *
 *    > 「自动展开」是导航的**辅助**，任何时候都不该压过用户的显式操作。
 *
 *    📌 React 版 `fe-v0.8.0` 第一版就写成了覆盖，实现时才改。
 *       这里直接写对。
 *
 * ⚠️ Vue 特有的一处：`v-model:open-keys` 是**双向**的，用户操作会直接写回
 *    这个 ref。所以 watch 的写入和用户的写入**竞争同一个 ref**——
 *    这正是必须「并入」而不是「覆盖」的额外理由。
 *    React 版是「受控 prop + onOpenChange」，两个方向是分开的。
 */
const openKeys = ref<string[]>([...active.value.openKeys])

watch(
  () => active.value.openKeys,
  (next) => {
    const added = next.filter((k) => !openKeys.value.includes(k))
    if (added.length > 0) openKeys.value = [...openKeys.value, ...added]
  },
)

function onClick({ key }: { key: string | number }) {
  /*
   * 目录节点的 key 是 `catalog-<id>`，点它只应展开/折叠，不该导航。
   * antdv 的 click 只会在叶子节点触发，但显式挡一道更稳。
   */
  const k = String(key)
  if (k.startsWith('/')) void router.push(k)
}
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

    <!--
      ⚠️ no_role 用户菜单为空。渲染一个空的 <Menu /> 会得到一片纯黑，
         用户无法区分「我没有权限」和「系统坏了」。
         空状态必须有文案——同 HomeRedirect。

      ⚠️ 这段文案 vue-v0.14.0 的 E2E 会断言，**必须与 React 版逐字相同**。
    -->
    <div
      v-if="auth.menus.length === 0 && !ui.siderCollapsed"
      style="
        padding: 16px 20px;
        color: rgba(255, 255, 255, 0.45);
        font-size: 13px;
        line-height: 1.8;
      "
    >
      你还没有任何菜单权限，<br />
      请联系系统管理员分配角色。
    </div>

    <Menu
      v-else-if="auth.menus.length > 0"
      theme="dark"
      mode="inline"
      :items="items"
      :selected-keys="active.selectedKeys"
      v-model:open-keys="openKeys"
      @click="onClick"
    />
  </LayoutSider>
</template>
