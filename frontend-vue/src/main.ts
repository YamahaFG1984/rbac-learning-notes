import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import 'ant-design-vue/dist/reset.css'
import './index.css'

const app = createApp(App)

/*
 * ⚠️ **注册顺序：pinia 必须在 router 之前。**
 *
 *    vue-v0.5.0 的导航守卫里要调 useAuthStore()。router 一旦被 use，
 *    首次导航可能立刻触发守卫——那时 pinia 必须已经就绪。
 *
 *    顺序写反的 bug **在本 tag 不会暴露**（还没有守卫），
 *    到 vue-v0.5.0 才炸，报错是
 *        getActivePinia() was called with no active Pinia
 *    ——看起来像忘了装 pinia，实际是注册顺序问题。
 *
 *    这是 V-ADR-003 那类问题的第一个现场：
 *    Pinia 的 store 绑在 app 实例上，而 React 版的 Zustand 是模块级单例，
 *    **根本不存在「什么时候可以用 store」这个问题。**
 */
app.use(createPinia())
app.use(router)

/*
 * 🔴 **刻意不写 `app.use(Antd)`。**
 *
 *    那是 Vue + Ant Design Vue 最常见的写法，也是本 tag 实测到的第一个真实问题：
 *
 *        app.use(Antd)  → 全局注册**所有**组件 → tree-shaking 失效
 *
 *    实测（vue-v0.1.0，只有一个占位页）：
 *        Vue   dist/assets 合计 **1.53 MB**   ← app.use(Antd)
 *        React dist/assets 合计 **1.24 MB**   ← 12 个页面、全部功能
 *
 *    **一个占位页比人家整个应用还大。**
 *
 *    正确做法是在用到的地方按需 import（antdv 4 是 CSS-in-JS，样式自动跟随）：
 *
 *        <script setup lang="ts">
 *        import { Button, Card } from 'ant-design-vue'
 *        </script>
 *        <template><Button>...</Button></template>
 *
 *    ⚠️ 代价是模板里写 `<Button>` 而不是 `<a-button>`，
 *       比「全局注册 + 短横线标签」啰嗦一点，也不那么「Vue 味」。
 *
 *    但 V-ADR-002（最小差异原则）要求这一处必须对齐 React 版的
 *    `import { Button } from 'antd'`——否则 vue-v1.0.0 的体积对比
 *    量出来的是「注册方式的差异」，而不是「框架的差异」。
 *
 *    📌 详见 04-React与Vue3做法对比.md 第 16 节。
 */

app.mount('#app')

// ⚠️ VueQueryPlugin 在 vue-v0.2.0 注册（登录用 useMutation）。
//    <ConfigProvider> 也在 vue-v0.2.0 —— 它要处理 autoInsertSpaceInButton
//    这个会让所有按文本查找按钮的测试失效的坑。
