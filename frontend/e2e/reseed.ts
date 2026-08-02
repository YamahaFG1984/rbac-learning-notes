import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const REPO_ROOT = resolve(process.cwd(), '..')

/**
 * 把演示数据恢复到已知基线。
 *
 * 🔴 为什么需要它：**E2E 跑在一个共享的、可变的数据库上。**
 *
 *    这一点我是踩了才想明白的。ticket-list.spec.ts 断言
 *    「superadmin 看到 80 条」——这个数字必须和后端的 SCOPE_MATRIX 一致，
 *    是这条测试全部的价值所在。
 *
 *    但 ticket-crud.spec.ts 会新建一张工单、删掉一张工单，
 *    而 Playwright 按文件名顺序跑，crud 在 list 前面。
 *    于是 80 变成了 80±1，测试红了——**而代码没有任何问题**。
 *
 *    症状极具迷惑性：单独跑每个文件都绿，全量跑随机红几条，
 *    每次红的还不一样。很容易被归因成「E2E 就是不稳定」，
 *    然后加 retry 把它盖掉——那等于把一个真实的设计缺陷变成噪音。
 *
 * ⚠️ 两种解法，我们选了后者：
 *
 *    a) 把断言改成相对的（先读基线再比较）
 *       —— 简单，但那条测试就不再能证明「前端条数 == 后端数据权限矩阵」了，
 *          而这正是它存在的理由。
 *
 *    b) 给需要确定基线的用例显式重置数据
 *       —— 多一步，但断言保持绝对，也就保持了它的价值。
 *
 *    **不要为了让测试变绿而削弱它的断言。**
 */
export function reseedDatabase() {
  execFileSync(
    '.venv/bin/python',
    ['manage.py', 'seed_demo', '--flush', '--noinput'],
    { cwd: REPO_ROOT, stdio: 'pipe' },
  )
}
