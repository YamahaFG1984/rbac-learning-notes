import { Button, Result } from 'antd'
import { useNavigate } from 'react-router'

type Kind = '403' | '404' | '500'

const PRESET: Record<Kind, { title: string; subTitle: string }> = {
  '403': { title: '403', subTitle: '你没有访问此页面的权限。如认为这是配置问题，请联系系统管理员。' },
  // ⚠️ 数据权限范围外的记录后端返回 404 而不是 403（后端 ADR-009），
  //    所以文案必须**同时覆盖两种情况且不泄露是哪一种**。
  '404': { title: '404', subTitle: '页面或数据不存在，或你无权访问。' },
  '500': { title: '500', subTitle: '服务器开小差了，请稍后重试。' },
}

export function ErrorResult({
  kind = '500',
  onRetry,
}: {
  kind?: Kind
  onRetry?: () => void
}) {
  const navigate = useNavigate()
  const preset = PRESET[kind]

  return (
    <Result
      status={kind}
      title={preset.title}
      subTitle={preset.subTitle}
      extra={
        <>
          {onRetry && (
            <Button type="primary" onClick={onRetry}>
              重试
            </Button>
          )}
          <Button onClick={() => navigate('/')}>返回首页</Button>
        </>
      }
    />
  )
}
