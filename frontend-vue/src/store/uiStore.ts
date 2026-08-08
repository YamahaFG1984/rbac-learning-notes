import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

/**
 * 纯客户端状态（F-ADR-005 / V-ADR-003）。
 *
 * 判据：这份数据的真相在哪？在浏览器 → Pinia；在数据库 → TanStack Query。
 * 侧边栏折叠、主题、表格列宽都没有服务端对应物，
 * 放进 Query 是概念错误（它管的是「服务端状态的缓存」）。
 *
 * 📌 一处小差异：**持久化。**
 *
 *    Zustand 自带 `persist` 中间件，React 版一行 `persist(..., { name: 'rbac-ui' })` 搞定。
 *    Pinia **没有内置持久化**，社区方案是 `pinia-plugin-persistedstate`。
 *
 *    这里选择手写 5 行而不是加一个依赖——V-ADR-002 要求两边的依赖尽量对齐，
 *    为一个 boolean 引入插件会让「Vue 装了 React 没有的东西」这件事
 *    出现在依赖清单上，而它其实与框架能力无关，只是电池自带程度不同。
 */
const STORAGE_KEY = 'rbac-ui-vue'

export const useUiStore = defineStore('ui', () => {
  const siderCollapsed = ref(readPersisted())
  // vue-v0.5.0 的导航守卫是 async 的，用它显示全局 loading
  const navigating = ref(false)

  function toggleSider() {
    siderCollapsed.value = !siderCollapsed.value
  }

  // ⚠️ 只持久化 siderCollapsed，**不持久化 navigating**——
  //    把瞬时状态写进 localStorage 会导致「刷新后一直转圈」。
  watch(siderCollapsed, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ siderCollapsed: v }))
    } catch {
      // 隐私模式下 localStorage 会抛异常。折叠状态丢了无所谓，不能让它崩掉应用。
    }
  })

  return { siderCollapsed, navigating, toggleSider }
})

function readPersisted(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? Boolean(JSON.parse(raw).siderCollapsed) : false
  } catch {
    return false
  }
}
