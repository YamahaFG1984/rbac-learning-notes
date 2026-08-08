import type { PermCode } from '@/constants/permissions'

import { useAuthStore } from './store'

/**
 * 唯一的权限判断入口。
 *
 * 参数类型是 `PermCode` 而不是 `string`（F-ADR-012 / V-ADR-008）——
 * 写错的权限码**编译期就报错**，不会像模板版那样静默地不渲染按钮。
 *
 * ⚠️ `<Can>`、路由守卫、菜单**全部**调这里，不重复实现。
 *    写两遍的话，将来加语法（比如「否定权限」）要改两处，
 *    而且很可能只改一处。超管的 `['*']` 通配也只在 store.can 里处理一次。
 *
 * 🟡 与 React 版的差异：
 *
 *    React 要 `useCallback` 包一层，否则每次渲染返回新函数，
 *    依赖它的 `useMemo` 全部失效——**「值的身份」也要管**。
 *
 *    Vue 不需要：函数本身不参与依赖追踪，被追踪的是它读到的 `perms`。
 *
 *    ⚠️ 但代价在别处：Vue 要管「这个值是不是响应式的」。
 *       调用方**必须**把结果放进 `computed`，否则求值一次就定死了：
 *
 *          ❌ const canDelete = can(PERM.X)              // 永远不更新
 *          ✅ const canDelete = computed(() => can(PERM.X))
 *
 *       两边都有一个额外维度要操心，只是维度不同。
 */
export function usePermission() {
  const auth = useAuthStore()

  return {
    can: (code: PermCode) => auth.can(code),
    canAny: (codes: PermCode[]) => codes.some((c) => auth.can(c)),
    canAll: (codes: PermCode[]) => codes.every((c) => auth.can(c)),
  }
}
