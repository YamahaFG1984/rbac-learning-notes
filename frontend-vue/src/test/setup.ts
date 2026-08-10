import '@testing-library/jest-dom/vitest'

import { createPinia, setActivePinia } from 'pinia'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import { resetVersionWatcher } from '@/api/versionWatcher'

import { resetMswState } from './msw/handlers'
import { server } from './msw/server'

/**
 * 🔴 每个测试前重建一个 Pinia 实例。
 *
 * 🟡 **与 React 版恰好相反的麻烦**（V-ADR-011）：
 *
 *      React（Zustand 是模块级单例）：
 *        useAuthStore.setState(INITIAL)      ← 必须手动 **reset**
 *
 *      Vue（Pinia 需要 active 实例）：
 *        setActivePinia(createPinia())        ← 必须手动 **创建**
 *
 *    两个都不能忘，但**忘了的表现相反**：
 *
 *      | | 忘了会怎样 | 难查程度 |
 *      | React | 测试**顺序相关**：单跑绿、全跑红、换个顺序又绿 | 🔴 极难 |
 *      | Vue   | **立即抛错**，报错直接说明原因 | 🟢 容易 |
 *
 *    📌 在**测试**这个场景里，「失败得响」是纯收益——
 *       顺序相关的测试是所有测试问题里最消耗时间的一类。
 *
 *    ⚠️ 但同一个「响」在生产代码里是白屏（VE-2.6）。**同一个特性，两种后果。**
 *
 * 对照后端 v0.16.0 的 tests/conftest.py 全局清缓存 fixture——
 * 同一个问题的三种语言版本：**有全局状态就必须管测试隔离**，
 * 否则出现「单独跑绿、一起跑红」。
 */
function reset() {
  setActivePinia(createPinia())
  // 模块级单例，不重置的话上一个测试的版本号会让下一个测试误判
  resetVersionWatcher()
  resetMswState()
}

beforeEach(reset)
afterEach(reset)

/**
 * ⚠️ `onUnhandledRequest: 'error'`
 *
 *    没被 mock 的请求直接失败，而不是悄悄放过去打真网络。
 *    放过去的话，测试在有网时绿、在 CI 里红，
 *    而且报错指向的是超时，不是「你忘了 mock 这个接口」。
 *
 * 🟢 这段与 React 版**逐字相同**——MSW 拦的是网络层，不认识 Vue 和 React。
 */
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
