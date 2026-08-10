import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * 🔴 **双前端对账 —— 本阶段新增，React 阶段不存在这个问题。**
 *
 * 现在有两个前端消费同一个后端契约。它们必须保持一致的东西：
 *
 *   1. 权限常量文件（由 `export_perm_constants` 生成）
 *   2. 服务端校验清单（由 `export_enforced_perms` 生成）
 *   3. MSW handlers 与 fixtures（同一份后端契约的 mock）
 *
 * ⚠️ **为什么不能只靠「两边各跑一次 `--check`」**（V-ADR-008 的代价那一节）：
 *
 *    `--check` 保证的是「每个前端各自与数据库一致」。
 *    但如果有人**手工编辑**了其中一个文件，`--check` 只在**跑了那一次**时发现；
 *    而直接 diff 两个文件是**结构性**的：只要不一致就红，
 *    不依赖谁记得跑哪个命令。
 *
 * ⚠️ 更重要的是它能发现一类 `--check` 根本看不见的问题：
 *    **其中一个前端忘了重新生成**。那时它与数据库不一致（`--check` 能发现），
 *    但如果 CI 只跑了另一个前端的 `--check`，就漏掉了。
 */

const ROOT = resolve(import.meta.dirname, '../../..')
const REACT = resolve(ROOT, 'frontend')
const VUE = resolve(ROOT, 'frontend-vue')

function read(base: string, rel: string) {
  return readFileSync(resolve(base, rel), 'utf8')
}

describe('🔴 两个前端的生成产物必须逐字节相同', () => {
  it('src/constants/permissions.ts', () => {
    expect(read(VUE, 'src/constants/permissions.ts')).toBe(
      read(REACT, 'src/constants/permissions.ts'),
    )
  })

  it('src/test/enforced-perms.json', () => {
    expect(read(VUE, 'src/test/enforced-perms.json')).toBe(
      read(REACT, 'src/test/enforced-perms.json'),
    )
  })
})

describe('🟢 与框架无关的测试基建必须逐字节相同', () => {
  /*
   * ⚠️ 这几条既是对账，也是**结论的证据**。
   *
   *    04 对比文档声称「MSW handlers 与框架无关，可以逐字复用」。
   *    那句话如果只写在文档里，半年后没人知道它还成不成立。
   *    写成断言之后，**哪天有人改动其中一份，这条就会红**——
   *    到时候要么同步另一份，要么承认「它其实与框架有关」并改文档。
   *
   *    > 一个能被测试守住的结论，才是活的结论。
   */
  it('src/test/msw/handlers.ts —— 它拦的是网络层，不认识 Vue 和 React', () => {
    expect(read(VUE, 'src/test/msw/handlers.ts')).toBe(
      read(REACT, 'src/test/msw/handlers.ts'),
    )
  })

  it('src/test/msw/server.ts', () => {
    expect(read(VUE, 'src/test/msw/server.ts')).toBe(read(REACT, 'src/test/msw/server.ts'))
  })

  it('src/test/fixtures.ts —— 演示数据的数字必须两边一致', () => {
    expect(read(VUE, 'src/test/fixtures.ts')).toBe(read(REACT, 'src/test/fixtures.ts'))
  })
})

describe('🟢 请求层与框架无关的部分', () => {
  /**
   * ⚠️ 这几个文件**不要求逐字节相同**（注释不同：Vue 版记了更多实测发现），
   *    但**去掉注释后的代码**必须相同。
   *
   *    这正是 V-ADR-001「不抽公共包」的意义：
   *    要证明两边一样，必须让它们真的各写一份，然后 diff。
   *    抽成公共包等于把结论藏进了工程结构里。
   */
  const stripComments = (s: string) =>
    s
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .join('\n')

  it.each([
    'src/api/csrf.ts',
    'src/api/errorHandlers.ts',
    'src/api/admin.ts',
    'src/api/tickets.ts',
    'src/auth/api.ts',
  ])('%s 去掉注释后与 React 版相同', (rel) => {
    expect(stripComments(read(VUE, rel))).toBe(stripComments(read(REACT, rel)))
  })
})
