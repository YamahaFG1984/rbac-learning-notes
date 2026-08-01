import '@testing-library/jest-dom/vitest'

import { afterEach, beforeEach } from 'vitest'

import { useAuthStore } from '@/auth/store'

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
    status: 'unknown',
  })
}

beforeEach(reset)
afterEach(reset)
