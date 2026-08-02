import '@testing-library/jest-dom/vitest'

import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import { useAuthStore } from '@/auth/store'
import { resetVersionWatcher } from '@/api/versionWatcher'

import { resetMswState } from './msw/handlers'
import { server } from './msw/server'

/**
 * 每个测试前后重置权限 store。
 *
 * 对照后端 v0.16.0 加的 tests/conftest.py 全局清缓存 fixture——
 * 同一个问题的两种语言版本：有全局状态就必须管测试隔离，
 * 否则出现「单独跑绿、一起跑红」。
 */
function reset() {
  useAuthStore.setState({
    user: null,
    perms: [],
    menus: [],
    knownRoutes: [],
    status: 'unknown',
  })
  // 模块级单例，不重置的话上一个测试的版本号会让下一个测试误判（fe-v0.13.0）
  resetVersionWatcher()
  resetMswState()
}

beforeEach(reset)
afterEach(reset)

/**
 * ⚠️ onUnhandledRequest: 'error'
 *
 *    没被 mock 的请求直接失败，而不是悄悄放过去打真网络。
 *    放过去的话，测试在有网时绿、在 CI 里红，
 *    而且报错指向的是超时，不是「你忘了 mock 这个接口」。
 */
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
