import { Button, Result } from 'antd'
import { useNavigate } from 'react-router'

/**
 * 🔴 数据不可见时的统一文案。
 *
 * 后端 ADR-009 决定：数据权限范围外的记录返回 **404 而不是 403**——
 * 403 会泄露「这条记录存在」，攻击者可以遍历 ID 画出数据库的 ID 分布。
 *
 * ⚠️ 前端如果把文案写成「工单不存在」，等于把后端的努力白费一半：
 *    用户（和攻击者）会以为这个 ID 真的没有。更糟的是，真正的管理员
 *    看到这个提示会去数据库里找，发现明明有，然后来报「系统 bug」。
 *
 * 统一文案「不存在或你无权访问」：
 *   - 不泄露是哪一种
 *   - 给了用户下一步动作的暗示（去找管理员）
 *
 * 对照模板版 v0.8.0 的 404.html：
 * 「如果你认为这是权限问题，请联系系统管理员」——同一个思路。
 */
export function ResourceNotFound({
  description = '如果你认为这是权限问题，请联系系统管理员。',
}: {
  description?: string
}) {
  const navigate = useNavigate()

  return (
    <Result
      status="404"
      title="不存在或你无权访问"
      subTitle={description}
      extra={
        <Button type="primary" onClick={() => navigate(-1)}>
          返回上一页
        </Button>
      }
    />
  )
}
