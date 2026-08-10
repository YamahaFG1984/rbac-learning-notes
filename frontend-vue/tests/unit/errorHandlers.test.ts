import type { AxiosError } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { configureErrorHandlers, handleApiError } from '@/api/errorHandlers'

function err(status?: number, detail?: string): AxiosError<{ detail?: string }> {
  return {
    response: status ? { status, data: detail ? { detail } : {} } : undefined,
  } as AxiosError<{ detail?: string }>
}

let h: {
  redirectToLogin: ReturnType<typeof vi.fn>
  refetchProfile: ReturnType<typeof vi.fn>
  warn: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  h = {
    redirectToLogin: vi.fn(),
    refetchProfile: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }
  configureErrorHandlers(h)
})

/**
 * 🔴 本文件存在的理由就是下面第一组用例。
 *
 * 「403 会不会跳登录页」是 SPA 里的高频 bug，一个字之差：
 *     if (status === 401 || status === 403) redirectToLogin()
 * 它值得有一条会跑的断言，而不是靠 code review 时有人注意到。
 */
describe('🔴 401 与 403 必须区别对待', () => {
  it('401 跳登录页', () => {
    expect(handleApiError(err(401))).toBe('unauthenticated')
    expect(h.redirectToLogin).toHaveBeenCalled()
  })

  it('🔴 403 **绝不**跳登录页', () => {
    handleApiError(err(403))
    // 跳的话就是那个死循环：403 → 登录 → 还是 403 → 登录 → …
    // 用户会以为账号坏了，而真实原因只是「他确实没这个权限」
    expect(h.redirectToLogin).not.toHaveBeenCalled()
  })

  it('401 **不**弹提示（用户马上会看到登录页）', () => {
    handleApiError(err(401))
    expect(h.warn).not.toHaveBeenCalled()
    expect(h.error).not.toHaveBeenCalled()
  })

  it('403 **要**弹提示（页面不会变，不说用户不知道发生了什么）', () => {
    handleApiError(err(403))
    expect(h.warn).toHaveBeenCalledWith('权限不足')
  })

  it('403 顺带重拉 profile —— 可能是权限刚被撤销', () => {
    handleApiError(err(403))
    expect(h.refetchProfile).toHaveBeenCalled()
  })

  it('401 不重拉 profile（都不知道你是谁了，拉了也没用）', () => {
    handleApiError(err(401))
    expect(h.refetchProfile).not.toHaveBeenCalled()
  })
})

describe('交给调用方的状态码', () => {
  it('🔴 404 不做任何全局处理', () => {
    // 全局弹 toast 的话，详情页会**既停在空白上又弹个提示**。
    // 正确处理取决于场景：详情页整页替换、列表页提示+刷新、后台请求可能什么都不做
    expect(handleApiError(err(404))).toBe('unhandled')
    expect(h.warn).not.toHaveBeenCalled()
    expect(h.error).not.toHaveBeenCalled()
    expect(h.redirectToLogin).not.toHaveBeenCalled()
  })

  it('400 也不处理 —— 由表单映射到字段上', () => {
    expect(handleApiError(err(400))).toBe('unhandled')
    expect(h.error).not.toHaveBeenCalled()
  })
})

describe('用后端的 detail，不硬编码文案', () => {
  it('403 优先显示后端说的话', () => {
    handleApiError(err(403, '你没有该操作的权限'))
    expect(h.warn).toHaveBeenCalledWith('你没有该操作的权限')
  })

  it('429 显示后端的限流文案', () => {
    handleApiError(err(429, '登录失败次数过多，请 15 分钟后再试'))
    expect(h.warn).toHaveBeenCalledWith('登录失败次数过多，请 15 分钟后再试')
  })

  it('没有 detail 时才用兜底文案', () => {
    handleApiError(err(429))
    expect(h.warn).toHaveBeenCalledWith('操作过于频繁，请稍后再试')
  })
})

describe('网络错误与服务端错误', () => {
  it('🔴 没有 response = 请求根本没到服务器', () => {
    expect(handleApiError(err())).toBe('network')
    // 显示成「服务器错误」会让用户去联系 IT，而真实原因可能是他 WiFi 断了
    expect(h.error).toHaveBeenCalledWith('网络连接失败，请检查网络后重试')
  })

  it('5xx 不弹 toast —— 交给错误边界整页替换', () => {
    expect(handleApiError(err(500))).toBe('server')
    expect(h.error).not.toHaveBeenCalled()
    expect(h.warn).not.toHaveBeenCalled()
  })

  it('502 / 503 同样处理', () => {
    expect(handleApiError(err(502))).toBe('server')
    expect(handleApiError(err(503))).toBe('server')
  })
})
