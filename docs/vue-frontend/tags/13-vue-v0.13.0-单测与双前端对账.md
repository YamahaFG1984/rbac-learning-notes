# vue-v0.13.0 — 单元测试、MSW 与**双前端对账**

| 项 | 值 |
| --- | --- |
| 需求 | VNFR-9、VAC-7 |
| 关键 V-ADR | [011](../02-设计文档.md) |
| 预计耗时 | 3 ~ 4 小时 |
| 变更规模 | ~450 行（几乎全是测试） |
| 上一个 tag | `vue-v0.12.0` |
| React 对应 | [`fe-v0.15.0`](../../frontend/tags/15-fe-v0.15.0-单元测试与MSW.md) |

---

## 一、动手之前，先自己想清楚

1. 测拦截器的 401 分流，用 `vi.mock('axios')` 还是 MSW？**为什么？**
2. Pinia 的 store 在测试之间会不会串？**怎么隔离？**
3. 哪些东西**不该**用单测测？
4. 🔴 两个前端的权限常量文件必须一致。**怎么保证？跑两次 `--check` 够吗？**

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/test/setup.ts` | 全局 `setActivePinia` |
| 新建 | `src/test/msw/handlers.ts` | ⚠️ **从 React 版逐字复制** |
| 新建 | `src/test/msw/server.ts` | 同上 |
| 新建 | `src/test/fixtures.ts` | 同上 |
| 新建 | `tests/unit/*.test.ts` | 纯函数、单组件 |
| 新建 | `tests/integration/*.test.ts` | 拦截器、认证流程（+ MSW） |
| 新建 | `tests/structural/permCoverage.test.ts` | 前后端权限码对账 |
| 新建 | 🔴 `tests/structural/crossFrontend.test.ts` | **双前端对账（本阶段新增）** |
| 新建 | `vitest.config.ts` | 覆盖率阈值 |

---

## 三、⚠️ 容易写错的地方

### 1. 第一节第 1 问：**MSW**，不 mock axios

> **MSW 拦网络层，不 `vi.mock('axios')`。**
> 我们有一半的权限逻辑在拦截器里，mock 掉 axios 它们**一行都不会执行**。

这条与框架无关，`frontend/CLAUDE.md` 第 7 节已经写死。
`handlers.ts` **逐字复制**——它拦的是 HTTP，不认识 Vue 和 React。

### 2. 🔴 第一节第 2 问：每个用例 `setActivePinia(createPinia())`

```ts
// src/test/setup.ts
beforeEach(() => {
  setActivePinia(createPinia())
})
```

**与 React 版恰好相反**：

```ts
// React：Zustand 是模块级单例 → 测试之间会串 → 必须手动 reset
beforeEach(() => useAuthStore.setState(INITIAL))

// Vue：Pinia 需要 active 实例 → 必须手动创建
beforeEach(() => setActivePinia(createPinia()))
```

**两个都不能忘，但忘了的表现相反**：

| | 忘了会怎样 | 难查程度 |
| --- | --- | --- |
| React | 测试**顺序相关**：单跑绿、全跑红、换个顺序又绿 | 🔴 极难 |
| Vue | **立即抛错**，报错直接说明原因 | 🟢 容易 |

> 📌 [04 对比文档第 14 节](../04-React与Vue3做法对比.md#14-测试两种相反的隔离麻烦)：
> **Vue 失败得更响，React 失败得更静。**
> 在测试这个场景里，失败得响是**纯收益**——顺序相关的测试是所有测试问题里最耗时的一类。

### 3. 断言时序：`nextTick` 而不是 `waitFor`

```ts
// React
await waitFor(() => expect(screen.getByText('删除')).toBeInTheDocument())

// Vue
store.perms = ['ticket:ticket:delete']
await nextTick()
expect(screen.getByText('删除')).toBeInTheDocument()
```

⚠️ **Vue 的确定性有上限**：链路里如果是「`watch` 触发 `watch`」，
一个 `nextTick` 不够，表现是「断言偶尔失败」。

→ 遇到就用 `await flushPromises()`，**不要靠加 `nextTick` 凑数**——
凑出来的数字下次改代码就不对了。

### 4. 第一节第 3 问：有些东西单测测不了，**别硬测**

| 测不了 | 为什么 | 谁来测 |
| --- | --- | --- |
| `document.cookie` 的 httpOnly 语义 | jsdom **不实现** httpOnly，断言会**假绿** | E2E |
| 绕过前端直调 API | 需要真后端 | E2E |
| 真实浏览器的 history 行为 | jsdom 是模拟的 | E2E |
| 动态路由在刷新后的时序 | 同上 | E2E |

> **硬测会写出「测了但没测到」的假测试**——比没有测试更糟，因为它给人安全感。

### 5. 必测清单（权限相关的部分要 ≥ 90%）

| 模块 | 测什么 |
| --- | --- |
| `usePermission` | 通配 `['*']`、精确匹配、不匹配、空 perms |
| `Can.vue` | 有权限渲染、无权限不渲染、**不传 prop 不渲染**、fallback 插槽 |
| `menuAdapter` | 树转换、空目录、图标兜底、高亮匹配（**含 `/tickets-archive` 用例**） |
| `buildRoutes` | 菜单树 → 路由记录、catalog 不产生路由、component 配错时降级 |
| `dynamic.ts` | 🔴 **注册后能匹配；`clearDynamicRoutes` 之后匹配不到** |
| `errorHandlers` | 401 跳登录、**403 不跳登录**、404 不处理、5xx |
| `versionWatcher` | 首次不 invalidate、变了才 invalidate、**新旧 perms 相同时不提示** |
| `formErrors` | 字段错误映射、`detail` 走通用提示 |
| `useTableQuery` | URL ↔ 参数、类型还原、`replace` |

⚠️ `dynamic.ts` 的那条是 **Vue 独有的**——React 版没有这个模块。
**必须有一条测试断言「登出后旧路由真的没了」**，否则 `VUS-6` 只有 E2E 能发现。

### 6. 结构性测试：前后端权限码对账

```ts
// tests/structural/permCoverage.test.ts —— 从 React 版复制，只改扫描后缀
// 扫 src/**/*.vue 里出现的 PERM.XXX，
// 对账 src/test/enforced-perms.json（由 export_enforced_perms 生成）
```

⚠️ 需要先跑：

```bash
python manage.py export_enforced_perms --out frontend-vue/src/test/enforced-perms.json
```

### 7. 🔴 第一节第 4 问：跑两次 `--check` **不够**

跑两次 `--check` 只能保证「每个前端各自与数据库一致」。
它**发现不了**「其中一个忘了重新生成，而数据库也没变」——
等等，那种情况下两边确实都一致。

真正的风险是**生成时机不同**：A 在权限点变更前生成，B 在变更后生成，
中间数据库变了两次又变回来……不现实。

**更实际的风险**：有人手工编辑了其中一个文件。
`--check` 会发现，但只在**跑了那一次**的时候。

→ **直接 diff 两个文件**，更强也更快：

```ts
// tests/structural/crossFrontend.test.ts
it('两个前端的权限常量文件逐字节相同', () => {
  const react = readFileSync('../frontend/src/constants/permissions.ts', 'utf-8')
  const vue = readFileSync('src/constants/permissions.ts', 'utf-8')
  expect(vue).toBe(react)
})

it('两个前端的 enforced-perms.json 相同', () => { /* 同上 */ })
```

⚠️ **`vue-v0.14.0` 还会加一条**：diff 两边 E2E 的 `SCOPE_MATRIX` / `PAGE_MATRIX`。

### 8. `no-client-side-filtering` 逐字复用

```ts
// 扫源码，禁止对列表结果做 .filter(...)
// V-ADR-015，与框架完全无关，只改扫描目录和后缀
```

### 9. 覆盖率阈值：**按模块设，不设一刀切**

```ts
// vitest.config.ts
coverage: {
  thresholds: {
    // 权限相关模块必须高
    'src/auth/**': { statements: 90, branches: 90 },
    'src/components/Can.vue': { statements: 90 },
    'src/api/**': { statements: 90 },
    'src/layouts/menuAdapter.ts': { statements: 90 },
    // ⚠️ 不设整体 80%。理由见下。
  },
}
```

> 📌 **React 版在这里发现规格书自相矛盾**：`fe-v0.15.0` 一边要求
> `src/router/** ≥ 90%`，一边在同一份文档里说「路由行为属于 E2E」。
> 最终结论是**按文件设阈值 + 写明理由**，整体覆盖率停在 22%。
>
> **Vue 版沿用这个结论，不重复那次纠结。**
> CRUD 页面由 E2E 覆盖，硬凑单测覆盖率只会产出「渲染了就算测过」的空测试。
>
> ⚠️ 但要**写明**：`VAC-7` 只要求「权限相关模块 ≥ 90%」，
> 已经从 `FAC-6`（整体 ≥ 80%）改过来了。**规格改了就改文档，不要让代码悄悄漂离。**

---

## 四、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `npm run test` | 全绿 |
| 2 | `npm run test:coverage` | 权限模块 ≥ 90% |
| 3 | 删掉 `setup.ts` 里的 `setActivePinia` | **立即抛错**（看一次，改回来） |
| 4 | 把 `errorHandlers` 的 403 改成跳登录 | 对应测试**变红** |
| 5 | 把 `Can.vue` 的默认值改成 `true` | 「不传 prop 不渲染」**变红** |
| 6 | 删掉 `clearDynamicRoutes` 的调用 | 对应测试**变红** |
| 7 | 手工改一个字符到 `permissions.ts` | 双前端对账**变红** |
| 8 | 在页面里用一个后端没有的 `PERM.XXX` | 编译期就报错 |
| 9 | `python manage.py export_perm_constants --check`（无参数） | 通过（**React 版没坏**） |
| 10 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 3~7 是「测试有没有真的在测东西」的验证。**
一条永远绿的测试不是测试，是装饰。

---

## 五、和我的实现对比什么

```bash
diff -u frontend/src/test/msw/handlers.ts frontend-vue/src/test/msw/handlers.ts   # 期望：空
diff -u frontend/src/test/fixtures.ts frontend-vue/src/test/fixtures.ts           # 期望：空
diff -u frontend/tests/unit/no-client-side-filtering.test.ts \
        frontend-vue/tests/unit/no-client-side-filtering.test.ts                  # 期望：只差后缀
```

| 对比点 | 想一想 |
| --- | --- |
| `handlers.ts` 差了几行 | 差了的话，你改了后端契约还是改了 mock？ |
| 有没有 `vi.mock('axios')` | 有的话，拦截器的哪些代码没被执行？ |
| 有没有测 httpOnly cookie | 测了的话，那条断言证明了什么？ |
| `dynamic.ts` 的清理测了吗 | 没测的话 `VUS-6` 只能靠 E2E |

---

## 六、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| MSW handlers / server / fixtures | 🟢🟢 **逐字节相同**（实测 `diff -q` 为空） |
| `errorHandlers.test.ts` | 🟢🟢 **逐字复用，14 条全绿**（它只跟状态码和回调打交道） |
| `authFlow.test.ts`（集成 + MSW） | 🟢🟢 **逐字复用，10 条全绿** |
| 不 mock axios | 🟢 **同一条铁律** |
| `no-client-side-filtering` | 🟢 只差扫描后缀 |
| `permCoverage` 结构性测试 | 🟡 改了**两处**（后缀 + 先去注释，见下） |
| **store 隔离** | 🔴 `setActivePinia` ← `setState(INITIAL)`；**麻烦方向相反** |
| 断言时序 | 🟡 `await nextTick()`（确定）← `waitFor`（轮询） |
| 组件渲染 | 🟡 `@testing-library/vue` ← `@testing-library/react`（API 几乎相同） |
| 覆盖率策略 | 🟢 **沿用 React 版的结论**，不重走一遍纠结 |
| **`dynamicRoutes.test.ts`** | 🔴🔴 **Vue 独有**（React 的路由表是 `f(menus)`，无从测起） |
| **`storeOutsideComponent.test.ts`** | 🔴🔴 **Vue 独有**（`VE-2.6`） |
| **双前端对账** | 🔴 **本阶段新增**（React 阶段不存在这个问题） |

### 📌 实测：哪些测试能逐字复用

| 文件 | 结果 |
| --- | --- |
| `src/test/msw/handlers.ts` | ✅ 逐字节相同 |
| `src/test/msw/server.ts` | ✅ 逐字节相同 |
| `src/test/fixtures.ts` | ✅ 逐字节相同 |
| `tests/unit/errorHandlers.test.ts` | ✅ **逐字节相同**，14 条全绿 |
| `tests/integration/authFlow.test.ts` | ✅ **逐字节相同**，10 条全绿 |

> **一份能跨框架复用的测试，说明它测的是「系统的行为」而不是「实现」。**
> 这五个文件加起来 24 条断言，一个字没改就在另一个框架上跑通了。

### 🔴📌 `permCoverage` 的扫描器有个弱点（React 版也有，只是没被触发）

第一次跑就红了：

```
offenders: ["undefined（用于 src/auth/usePermission.ts）"]
```

原因是我在 `usePermission.ts` 的**注释**里写了 `PERM.X` 举例，
而扫描器用正则直接扫源码文本，把注释也算进去了。

**React 版的扫描器有同样的弱点**，只是它的源码里恰好没有出现
「注释里写 `PERM.XXX`」的情况，所以一直没被触发。

修法：扫描前先 `stripComments()`。
📌 这是本阶段第 4 次「接下一个前端时发现上一个实现里没人验证过的地方」。

### 📌 双前端对账测了什么

```
🔴 生成产物逐字节相同：permissions.ts、enforced-perms.json
🟢 测试基建逐字节相同：msw/handlers、msw/server、fixtures
🟢 请求层去掉注释后相同：csrf、errorHandlers、admin、tickets、auth/api
```

⚠️ 最后一组**不要求逐字节相同**（Vue 版注释里记了更多实测发现），
但**去掉注释后的代码**必须相同。

> 这正是 [V-ADR-001](../02-设计文档.md)「不抽公共包」的意义：
> **要证明两边一样，必须让它们真的各写一份，然后 diff。**
> 抽成公共包等于把结论藏进了工程结构里。
>
> 而且这几条断言让结论变成**活的**：哪天有人改动其中一份，
> 这条就会红——到时候要么同步另一份，要么承认「它其实与框架有关」并改文档。

### 📌 一条只有覆盖率能发现的缺口

`menuAdapter.ts` 的 `functions` 卡在 88.88%，缺的是 `.sort()` 的比较函数——
它**只在两条前缀同时匹配时才执行**，而那正是「取最长的」这条规则存在的理由。

补上 `/system` 与 `/system/users` 同时匹配的用例之后才达标。

> ⚠️ 没有这条用例的话：比较函数一次都不跑，**把它写反（`a - b`）测试照样全绿**。
> 覆盖率在这里的作用不是「数字好看」，而是**指出了一条没被执行过的规则**。

**结果**：103 个单测、13 个文件全绿，全部按文件阈值达标。
整体覆盖率 ~17%（页面交给 E2E，同 React 版的取舍）。

---

## 七、延伸思考

1. `handlers.ts` 在两个前端里逐字相同。**这说明 MSW 在测什么层？**
   如果一份 mock 能同时服务两个框架，那它 mock 的是不是「正确的东西」？
   反过来：如果你的 mock 换框架就要改，说明什么？

2. Vue 忘了 `setActivePinia` 会立即抛错，React 忘了 reset 会产生顺序相关的测试。
   **「失败得响」在哪些场景下反而是缺点？**
   （提示：想想 `VE-2.6`——同一个「响」在生产代码里是白屏。）

3. 覆盖率整体只有 20% 出头，但权限模块 ≥ 90%。
   **这个数字该怎么向团队解释？**
   如果有人要求「必须 80%」，你会怎么回应？

4. 用例 3~7 是「变异测试」的手工版：故意改坏代码，看测试红不红。
   **能不能把它自动化？** 值得吗？
