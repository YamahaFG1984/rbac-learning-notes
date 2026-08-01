import type { ReactNode } from 'react'

import { Button, Result } from 'antd'
import type { AxiosError } from 'axios'

import { FullPageSpin } from '@/components/FullPageSpin'

import { useAuthStore } from './store'
import { useProfileQuery } from './useProfileQuery'

/**
 * 应用级引导：拉 profile，在拿到结果之前**不渲染任何东西**（FE-2.3）。
 *
 * ⚠️ 位置很关键：它必须在 RequireAuth 的**外面**。
 *
 *    第一版我把它放进了受保护区内部，结果是死锁——
 *    RequireAuth 看到 status === 'unknown' 就只渲染 spinner，
 *    于是 AuthBootstrap 永远不挂载，profile 永远不发请求，
 *    status 永远是 unknown。转圈转到天荒地老。
 *
 *    **「谁负责触发认证状态的确定」必须在「谁依赖这个状态」之上。**
 *
 * ⚠️ 另一个要点：**401 不是错误**。
 *    未登录用户拉 profile 拿到 401 是完全正常的流程，
 *    此时应该正常渲染 children，让路由把他送去登录页。
 *    只有网络错误 / 5xx 才该显示错误页。
 */
export function AuthBootstrap({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const { error, isError, isFetching, refetch } = useProfileQuery()

  const httpStatus = (error as AxiosError | null)?.response?.status

  // 401 =「你没登录」，是正常状态而不是故障
  if (isError && httpStatus !== 401) {
    return (
      <Result
        status="warning"
        title="无法加载你的权限信息"
        subTitle="请检查网络后重试。在权限信息加载成功之前，系统不会展示任何业务界面。"
        extra={
          <Button type="primary" onClick={() => void refetch()} loading={isFetching}>
            重试
          </Button>
        }
      />
    )
  }

  // 「还没问过后端」≠「确定未登录」。
  //
  // 这是「让默认状态是安全的」在前端的形态：**未知 ≠ 允许**。
  // 看似「初始 perms 是空数组，恰好等价于无权限，先渲染也没事」——
  // 这个侥幸才最危险：只要有人写出
  //     perms.length === 0 ? 显示全部 : 按权限显示
  // （理由是「还没加载完就先都显示吧」），就会真的闪现越权内容。
  // 干脆不挂载，就不存在这个口子。
  if (status === 'unknown') return <FullPageSpin tip="正在加载权限信息" />

  return <>{children}</>
}
