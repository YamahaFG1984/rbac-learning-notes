import type { Directive } from 'vue'

import { useAuthStore } from '@/auth/store'
import type { PermCode } from '@/constants/permissions'

/**
 * ⚠️⚠️ **这份代码不注册、不使用。它是 VE-4.5 的证据，不是可用方案。**
 *
 * 几乎所有「Vue + 权限管理」的教程都会给出这个：
 *
 *     <a-button v-perm="PERM.TICKET_TICKET_DELETE" danger>删除</a-button>
 *
 * 比 `<Can>` 优雅得多。**本项目明确拒绝它**（V-ADR-007），三条理由，
 * 每一条都在 vue-v0.7.0 实测复现过，记录见
 * `docs/vue-frontend/notes/指令方案评估.md`。
 *
 * ─────────────────────────────────────────────────────────────
 * 缺陷 1：先渲染，再删除
 *
 *   指令的 mounted 在元素**已经挂载到 DOM 之后**才执行。
 *   所以实际行为是「渲染出来 → 发现没权限 → 把它删掉」。
 *
 *   对普通元素这只是一帧闪烁；但按钮上如果有 autofocus、
 *   有 @vue:mounted、有埋点上报，**副作用已经发生了**。
 *   `<Can>` 内部用 v-if，元素**根本不会被创建**。
 *
 * ─────────────────────────────────────────────────────────────
 * 缺陷 2：🔴 删掉之后回不来（**致命**）
 *
 *   被指令删掉的元素**已经不在虚拟 DOM 树上**，
 *   updated 钩子不会再被调用。
 *
 *   于是 vue-v0.11.0 的权限变更感知在指令方案下**无法实现**：
 *     管理员撤销权限 → 按钮消失（本来就没渲染或已被删）
 *     管理员**恢复**权限 → 按钮**永远不回来**，除非刷新整页
 *
 *   不是「难实现」，是**做不到**。这一条单独就足以否决它。
 *
 * ─────────────────────────────────────────────────────────────
 * 缺陷 3：类型收窄失效
 *
 *   指令值的类型是 DirectiveBinding['value']，即 any：
 *
 *     <a-button v-perm="'ticket:ticket:delet'">删除</a-button>   ✅ 编译通过
 *
 *   F-ADR-012 说过：
 *     「TypeScript 在编译期挡住权限码 typo，**这是 SPA 相比模板版
 *       唯一在权限安全性上更强的地方**」
 *
 *   用了指令，这个唯一的优势就原地退回去了——退回到 Django 模板
 *   `{% if 'ticket:ticket:delet' in perms %}` 的水平。
 *
 *   而 `<Can :perm="...">` 的 prop 类型是 PermCode，写错**编译不过**。
 *
 * ─────────────────────────────────────────────────────────────
 * 📌 结论不是「指令不好」。
 *
 *    指令是个好机制——v-focus、v-resize、v-click-outside 用它都很合适：
 *    它们**不参与条件渲染、不需要类型收窄、也不需要在状态变化后恢复**。
 *
 *    权限场景恰好把这三条全占了。
 *
 *    **「Vue 能做而 React 不能做的事」不等于「Vue 应该这么做」。**
 */
export const vPerm: Directive<HTMLElement, PermCode> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    if (!auth.can(binding.value)) {
      // 元素此时已经在 DOM 里了 —— 这就是缺陷 1。
      el.parentElement?.removeChild(el)
      // 缺陷 2：删掉之后这个元素脱离了虚拟 DOM，
      //         updated 永远不会再被调用，权限恢复也回不来。
    }
  },
}
