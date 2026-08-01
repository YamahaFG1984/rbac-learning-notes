import type { ReactNode } from 'react'

import { usePermission } from '@/auth/usePermission'
import type { PermCode } from '@/constants/permissions'

interface CanProps {
  /** 单个权限码。⚠️ 类型是 PermCode 不是 string —— 写错编译期就报错 */
  perm?: PermCode
  /** 任一满足即可 */
  anyOf?: PermCode[]
  /** 全部满足才行 */
  allOf?: PermCode[]
  /** 无权限时渲染什么。默认 null（什么都不渲染） */
  fallback?: ReactNode
  children: ReactNode
}

/**
 * 按钮级权限。
 *
 * ⚠️⚠️ 这是**体验优化，不是安全边界。**
 *
 *    隐藏了「删除」按钮的用户**照样能删除**——
 *    perms 就在他的浏览器内存里，控制台改成 ['*'] 只需要几秒。
 *
 *    > 模板版：攻击者不点你的按钮，他直接发请求。
 *    > SPA 版：他连你的前端都不用。
 *
 *    唯一的安全边界是后端的 HasPerm + ScopedQuerysetMixin。
 *    **每一个 <Can> 都必须有一个对应的后端校验，成对出现，缺一不可。**
 *    fe-v0.16.0 会用 E2E 把这件事钉死：按钮不可见 + 直接发请求得到 403。
 *
 * ⚠️ 内部调用 usePermission()，不重新实现判断逻辑。
 *    写两遍的话，将来加语法（比如「否定权限」）要改两处，
 *    而且很可能只改一处。
 */
export function Can({ perm, anyOf, allOf, fallback = null, children }: CanProps) {
  const can = usePermission()

  /*
   * ⚠️ 什么都不传时**不渲染**。
   *
   *    「默认渲染」看起来更宽容，但它会让「写漏了 perm」静默通过——
   *    这正是后端 ADR-002「默认拒绝」在前端的形态：
   *    让默认状态是安全的，写漏立刻可见。
   */
  const ok = perm
    ? can(perm)
    : anyOf
      ? anyOf.some(can)
      : allOf
        ? allOf.every(can)
        : false

  return <>{ok ? children : fallback}</>
}
