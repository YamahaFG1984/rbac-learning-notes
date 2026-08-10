import type { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'

import { parseServerDetail, parseServerFieldErrors } from '@/utils/formErrors'

function err(data: unknown): unknown {
  return { response: { data } } as AxiosError
}

/**
 * 🟡 与 React 版 `formErrors.test.ts` 的差异：**只在最后一步**。
 *
 *    React 的 `applyServerFieldErrors(form, error)` 直接调 antd 的
 *    `form.setFields()`，测试里断言 `setFields` 被怎么调用。
 *    antdv 没有这个命令式 API，Vue 版的函数只负责**解析**，
 *    所以这里断言的是解析结果。
 *
 *    **解析逻辑（DRF 的错误体形状、区分 detail 与字段错误）两边完全相同。**
 *    这是 UI 库能力的差异，不是 Vue/React 的差异。
 */
describe('parseServerFieldErrors —— 不在前端复制业务规则', () => {
  it('DRF 的字段错误映射成 {字段: 首条文案}', () => {
    expect(parseServerFieldErrors(err({ title: ['该字段不能为空。'] }))).toEqual({
      title: '该字段不能为空。',
    })
  })

  it('多个字段', () => {
    expect(parseServerFieldErrors(err({ a: ['x'], b: ['y'] }))).toEqual({ a: 'x', b: 'y' })
  })

  it('🔴 `detail` 是非字段错误，**不塞进字段里**', () => {
    // 塞进去的话「没有任何一个输入框变红」，用户完全不知道哪里错了
    expect(parseServerFieldErrors(err({ detail: '权限不足' }))).toBeNull()
  })

  it('detail 与字段错误共存时，只取字段错误', () => {
    expect(parseServerFieldErrors(err({ detail: 'x', title: ['y'] }))).toEqual({ title: 'y' })
  })

  it('非对象响应体返回 null（交给调用方走通用提示）', () => {
    expect(parseServerFieldErrors(err('boom'))).toBeNull()
    expect(parseServerFieldErrors({})).toBeNull()
  })

  it('值不是数组时也能取到（后端偶尔返回字符串）', () => {
    expect(parseServerFieldErrors(err({ title: '直接是字符串' }))).toEqual({
      title: '直接是字符串',
    })
  })
})

describe('parseServerDetail', () => {
  it('取出 detail', () => {
    expect(parseServerDetail(err({ detail: '权限不足' }))).toBe('权限不足')
  })

  it('没有 detail 时返回 null', () => {
    expect(parseServerDetail(err({ title: ['x'] }))).toBeNull()
    expect(parseServerDetail({})).toBeNull()
  })
})
