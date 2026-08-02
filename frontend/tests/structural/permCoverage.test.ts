import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import enforced from '@/test/enforced-perms.json'
import { PERM } from '@/constants/permissions'

/**
 * 🔴 前后端权限码对账。
 *
 * 对照后端 v0.10.0 的那条结构性测试：
 *   「模板里有几个 `in perms`，视图层就该有几个对应的 @require_perm。」
 *
 * 这里守的是 CLAUDE.md 安全红线 2：
 *   模板隐藏按钮不是安全边界。每一个受控按钮，必须有对应的服务端校验。
 *   **成对出现，缺一不可。**
 *
 * 「成对出现」光靠人看是守不住的，所以把它写成会跑的断言。
 */

const SRC = resolve(import.meta.dirname, '../../src')

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return walk(full)
    return /\.tsx?$/.test(full) ? [full] : []
  })
}

/** 收集源码里所有 `PERM.XXX` 的引用 */
function collectUsedConstants(): Map<string, string[]> {
  const used = new Map<string, string[]>()

  for (const file of walk(SRC)) {
    if (file.includes('/constants/permissions.ts')) continue
    const source = readFileSync(file, 'utf8')
    for (const match of source.matchAll(/\bPERM\.([A-Z0-9_]+)\b/g)) {
      const name = match[1]
      used.set(name, [...(used.get(name) ?? []), file.replace(SRC, 'src')])
    }
  }
  return used
}

const USED = collectUsedConstants()
const ENFORCED = new Set(enforced.enforced)

describe('前端用到的权限码，后端都存在', () => {
  it('扫描确实找到了引用（自证有效）', () => {
    // ⚠️ 一条「什么都没找到」的检查，扫错目录时看起来和扫对目录一样绿
    expect(USED.size).toBeGreaterThan(10)
  })

  it('每个 PERM.XXX 都在生成的常量表里', () => {
    const known = new Set(Object.keys(PERM))
    const unknown = [...USED.keys()].filter((name) => !known.has(name))

    // TypeScript 本来就会挡住这种错误，但常量文件可能过期
    // （后端删了一个权限点、忘了重新生成）——那时 TS 也拦不住
    expect(unknown).toEqual([])
  })
})

describe('🔴 前端管的，后端也必须管（安全红线 2）', () => {
  it('每个前端使用的权限码，服务端都真的在校验', () => {
    const offenders: string[] = []

    for (const [name, files] of USED) {
      const code = PERM[name as keyof typeof PERM]
      if (!ENFORCED.has(code)) {
        offenders.push(`${code}（用于 ${files.join(', ')}）`)
      }
    }

    /*
     * 这条测试抓的是最危险的一类漏：
     *
     *   <Can perm={PERM.TICKET_TICKET_DELETE}>   ← 前端藏了按钮
     *   # 后端 destroy 忘了写进 perm_map        ← 服务端根本没拦
     *
     * 权限码存在、TypeScript 编译通过、界面看起来完全正确，
     * 而那个接口是裸奔的。前端的隐藏给了所有人一种安全的错觉。
     */
    expect(offenders).toEqual([])
  })

  it('对账清单本身是有内容的（自证有效）', () => {
    expect(ENFORCED.size).toBeGreaterThan(15)
  })
})

/**
 * 📌 **诚实地说明这个对账做不到什么。**
 *
 * 它比对的是「码的集合」，不是「哪个接口用了哪个码」。所以：
 *
 *   ✅ 抓得住：前端管了、后端**完全没管**这个码
 *   ❌ 抓不住：后端管了，但管在了**另一个接口**上
 *              （比如删除按钮用 delete 码，而后端只在导出接口上校验了它）
 *
 * 要抓住后者，导出的清单得带上路由，对账时还要知道每个按钮对应哪个接口——
 * 那是另一个量级的工作，且需要前端声明「这个按钮会调哪个接口」。
 *
 * 真正兜住这一层的是 fe-v0.16.0 的越权矩阵 E2E：
 * 它不看代码，直接拿每个角色去打每个接口。
 *
 * **知道自己抓不住什么，比假装全覆盖好。**
 */
describe('已知缺口', () => {
  it('记录：本对账不校验「码与接口的对应关系」', () => {
    // 这条测试永远绿，它的作用是让上面那段说明出现在测试报告里，
    // 而不是躺在一个没人读的注释里
    expect(true).toBe(true)
  })
})
