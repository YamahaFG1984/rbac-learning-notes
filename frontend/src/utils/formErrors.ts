import type { FormInstance } from 'antd'
import type { AxiosError } from 'axios'

/**
 * 把后端返回的字段错误映射回表单。
 *
 * ⚠️ 存在的意义是**不要在前端复制一份业务规则**。
 *
 *    「标题不能超过 128 字符」如果写死在前端，后端改成 256 时前端不知道，
 *    用户会被一条早就不存在的规则拦住——而且这种 bug 没人会去查前端。
 *
 *    前端只做必填、类型这类**纯体验**校验；业务规则一律以后端为准，
 *    失败了就把后端说的话原样显示出来。
 *
 * DRF 的字段错误格式：{ "title": ["该字段不能为空。"] }
 * 非字段错误（如 { "detail": "..." }）交给调用方处理。
 */
export function applyServerFieldErrors(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: FormInstance<any>,
  error: unknown,
): boolean {
  const data = (error as AxiosError<Record<string, unknown>>).response?.data
  if (!data || typeof data !== 'object') return false

  const fields = Object.entries(data).map(([name, errors]) => ({
    name,
    errors: Array.isArray(errors) ? errors.map(String) : [String(errors)],
  }))
  if (fields.length === 0) return false

  form.setFields(fields)
  return true
}
