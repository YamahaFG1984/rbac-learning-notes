import type { FormInstance } from 'antd'
import { describe, expect, it, vi } from 'vitest'

import { applyServerFieldErrors } from '@/utils/formErrors'

function fakeForm() {
  return { setFields: vi.fn() } as unknown as FormInstance & {
    setFields: ReturnType<typeof vi.fn>
  }
}

describe('applyServerFieldErrors', () => {
  it('把 DRF 的字段错误映射到表单项上', () => {
    const form = fakeForm()
    const ok = applyServerFieldErrors(form, {
      response: { data: { title: ['该字段不能为空。'] } },
    })

    expect(ok).toBe(true)
    expect(form.setFields).toHaveBeenCalledWith([
      { name: 'title', errors: ['该字段不能为空。'] },
    ])
  })

  it('字符串形式的错误也能处理', () => {
    const form = fakeForm()
    applyServerFieldErrors(form, {
      response: { data: { detail: '你尚未归属任何部门，无法创建工单' } },
    })
    expect(form.setFields).toHaveBeenCalledWith([
      { name: 'detail', errors: ['你尚未归属任何部门，无法创建工单'] },
    ])
  })

  it('多个字段一起映射', () => {
    const form = fakeForm()
    applyServerFieldErrors(form, {
      response: { data: { title: ['太长了'], status: ['无效选项'] } },
    })
    expect(form.setFields).toHaveBeenCalledWith([
      { name: 'title', errors: ['太长了'] },
      { name: 'status', errors: ['无效选项'] },
    ])
  })

  it('没有 response 时返回 false，不调 setFields', () => {
    const form = fakeForm()
    expect(applyServerFieldErrors(form, new Error('boom'))).toBe(false)
    expect(form.setFields).not.toHaveBeenCalled()
  })

  it('空对象返回 false', () => {
    const form = fakeForm()
    expect(applyServerFieldErrors(form, { response: { data: {} } })).toBe(false)
    expect(form.setFields).not.toHaveBeenCalled()
  })
})
