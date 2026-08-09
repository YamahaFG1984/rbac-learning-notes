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
 * DRF 的字段错误格式：`{ "title": ["该字段不能为空。"] }`
 * 非字段错误（如 `{ "detail": "..." }`）交给调用方处理。
 *
 * 🔴 与 React 版的差异：**返回值形状不同，因为 antdv 没有 `form.setFields()`。**
 *
 *    React（antd）：`form.setFields([{ name, errors }])` —— 命令式，
 *      表单实例自己持有校验状态，一句话搞定。
 *
 *    antdv：`Form` 的校验状态**由 rules 驱动**，没有对应的命令式注入 API。
 *      所以这里只负责**解析**，把 `{ 字段名: 错误文案 }` 交回给调用方，
 *      调用方拿它去驱动 `<FormItem :help>` / `:validate-status`。
 *
 *    → 核心逻辑（解析 DRF 的错误体、区分字段错误与 detail）**两边完全相同**；
 *      不同的只是最后一步「怎么把结果喂给表单」。
 *      **这是 UI 库能力的差异，不是 Vue/React 的差异。**
 */
export type FieldErrors = Record<string, string>

export function parseServerFieldErrors(error: unknown): FieldErrors | null {
  const data = (error as AxiosError<Record<string, unknown>>).response?.data
  if (!data || typeof data !== 'object') return null

  const out: FieldErrors = {}
  for (const [name, errors] of Object.entries(data)) {
    // `detail` 是非字段错误（DRF 的通用错误体），不属于任何一个输入框，
    // 交给调用方走 message.error —— 塞进字段里会「没有任何一个框变红」。
    if (name === 'detail') continue
    out[name] = Array.isArray(errors) ? String(errors[0]) : String(errors)
  }

  return Object.keys(out).length > 0 ? out : null
}

/** 非字段错误（`{ "detail": "..." }`），由调用方弹提示。 */
export function parseServerDetail(error: unknown): string | null {
  const data = (error as AxiosError<{ detail?: unknown }>).response?.data
  const detail = data?.detail
  return typeof detail === 'string' ? detail : null
}
