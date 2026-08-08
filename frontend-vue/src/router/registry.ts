import type { Component } from 'vue'

/**
 * 组件注册表：把后端下发的 `component` 字符串映射成懒加载组件。
 *
 * ⚠️ `import.meta.glob` 的路径**必须是字面量**——Vite 做的是静态分析，
 *    拼接出来的路径它看不见，`modules` 会是空对象，所有页面都加载不出来。
 *
 *    这和 Tailwind 扫描不到拼接 class 名是同一类问题
 *    （后端 v0.8.0 陷阱 4）：**构建工具做静态分析，运行时拼的东西它不知道。**
 *
 * 📌 **本文件与 React 版（frontend/src/router/registry.ts）只差两处**：
 *    文件后缀 `.vue` ← `.tsx`，以及不需要 `lazy()` 包装
 *    （Vue Router 直接吃「返回 Promise 的函数」）。
 *
 *    `import.meta.glob` 是 **Vite** 的能力，不是 React 或 Vue 的——
 *    「后端下发组件名 → 前端懒加载」这个模式的实现，**与框架完全无关**。
 */
const modules = import.meta.glob('../pages/**/*.vue')

export function resolveComponent(component: string | null) {
  if (!component) return null

  const key = `../pages/${component}.vue`
  const loader = modules[key]
  if (!loader) {
    // 后端把 component 配错了。**不能让整个应用崩**——降级成 null，
    // 由调用方渲染一个提示页，其余页面照常。
    // 同后端 v0.11.0 对 NoReverseMatch 的处理思路。
    console.error(`[router] 找不到组件：${key}（后端 component 字段配错了？）`)
    return null
  }

  return loader as () => Promise<{ default: Component }>
}
