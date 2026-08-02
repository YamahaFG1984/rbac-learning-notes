import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * 🔴 结构性测试：前端**不允许**对服务端返回的列表再过滤一次。
 *
 * 对应后端 tests 里那几条「模板里有几个 in perms，视图层就该有几个装饰器」
 * 的结构性测试——它们守的都不是某个行为，而是一条**架构约束**。
 *
 * 为什么这条约束值得用测试守（F-ADR-015）：
 *
 *   | 后果 | 说明 |
 *   | 分页错乱 | 后端说 50 条，前端筛掉 10 条，分页器还显示 50 |
 *   | 统计对不上 | 列表显示 40，导出 50 |
 *   | **零安全价值** | 数据早就到浏览器了，过滤发生在数据到达之后 = 没过滤 |
 *
 * 它很容易在某次「加个保险」的 code review 里被悄悄写回去，
 * 而且写回去之后短期内一切正常——直到有人对不上数字。
 */
// ⚠️ 路径解析在这类「扫源码」的测试里意外地容易出错：
//    · new URL('../../src', import.meta.url).pathname —— vitest 转换后的
//      import.meta.url 不一定是 file:// URL，会解析成 '/src'
//    · resolve(process.cwd(), 'src') —— 从仓库根目录跑 vitest 时 cwd 不是
//      frontend/，扫到的是一个不存在的目录，测试**静默通过**（扫了 0 个文件）
//
//    一条「什么都没找到」的测试，扫错目录时看起来和扫对目录一样绿。
//    所以下面还有一条断言：至少要扫到 N 个文件。
const SRC = resolve(import.meta.dirname, '../../src')

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return walk(full)
    return /\.tsx?$/.test(full) ? [full] : []
  })
}

/** 对「服务端返回的集合」做过滤的写法 */
const FORBIDDEN = [
  /\bresults\s*\.\s*filter\s*\(/,
  /\bdata\s*\.\s*results\s*\.\s*filter\s*\(/,
  /\bdata\s*\?\.\s*results\s*\.\s*filter\s*\(/,
]

describe('F-ADR-015：前端不做数据的二次过滤', () => {
  it('src/ 下没有对 results 的 filter 调用', () => {
    const offenders: string[] = []
    const files = walk(SRC)

    // ⚠️ 先证明自己确实扫到了东西 —— 扫错目录的话上面的循环一次都不进，
    //    offenders 为空，测试照样绿。
    expect(files.length).toBeGreaterThan(20)

    for (const file of files) {
      const source = readFileSync(file, 'utf8')
      for (const pattern of FORBIDDEN) {
        if (pattern.test(source)) {
          offenders.push(`${file.replace(SRC, 'src')} —— ${pattern}`)
        }
      }
    }

    expect(offenders).toEqual([])
  })

  it('正则本身有效 —— 用一段反例证明它抓得住', () => {
    // ⚠️ 一条「什么都没找到」的测试必须自证有效，
    //    否则正则写错时它会永远绿。同 fe-v0.9.0 的对照组。
    const bad = 'const visible = data.results.filter((t) => canSee(t))'
    expect(FORBIDDEN.some((p) => p.test(bad))).toBe(true)
  })
})
