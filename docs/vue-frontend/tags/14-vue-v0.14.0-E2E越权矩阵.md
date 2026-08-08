# vue-v0.14.0 — 🎯 E2E 越权矩阵（断言逐字相同）

| 项 | 值 |
| --- | --- |
| 需求 | VNFR-10、VAC-6、VAC-8 |
| 关键 V-ADR | [012](../02-设计文档.md) |
| 预计耗时 | 2.5 ~ 3 小时 |
| 变更规模 | ~400 行（几乎全是从 React 版复制） |
| 上一个 tag | `vue-v0.13.0` |
| React 对应 | [`fe-v0.16.0`](../../frontend/tags/16-fe-v0.16.0-E2E越权矩阵.md) |

> 🎯 **本 tag 的验收标准很特别：改动越少越好。**
>
> `VAC-8` 要求「断言值与 React 版逐字相同」。
> 如果你发现自己在改断言，**先停下来问：是前端有 bug，还是这条断言本来就测的是实现？**

---

## 一、动手之前，先自己想清楚

1. E2E 里要断言「cs_staff 直接 DELETE 一个工单被拒」。**请求要带什么头？**
   不带会怎样？
2. React 版为了篡改 store，在 e2e 构建里挂了 `window.__AUTH_STORE__`。
   **Vue 版需要吗？**
3. E2E 跑在共享的数据库上。会改数据的 spec 要做什么？
4. E2E 跑 dev server 还是生产构建？为什么？

---

## 二、交付物清单

| 操作 | 文件 | 说明 |
| --- | --- | --- |
| 复制 | `e2e/helpers.ts` | 只改端口 |
| 复制 | `e2e/reseed.ts` | **逐字** |
| 复制 | `e2e/matrix.spec.ts` | 🎯 **逐字**（断言一个不改） |
| 复制 | `e2e/bypass.spec.ts` | 只改篡改方式 |
| 复制 | `e2e/menu.spec.ts` 等 | 少数选择器 |
| 新建 | `playwright.config.ts` | `baseURL: 5174` |
| 新建 | `scripts/e2e-vue.sh` | 一键跑 |
| 新建 | `tests/structural/matrixParity.test.ts` | 🔴 diff 两边的矩阵常量 |
| 修改 | `vite.config.ts` | `--mode e2e`（如果需要） |

---

## 三、⚠️ 容易写错的地方

### 1. 🔴 第一节第 1 问：**必须带 `X-CSRFToken`**，否则是**假绿**

```ts
async function csrfHeaders(page: Page) {
  const cookies = await page.context().cookies()
  const token = cookies.find((c) => c.name === 'csrftoken')?.value ?? ''
  return { 'X-CSRFToken': token }
}

const res = await page.request.delete(`/api/v1/tickets/${id}/`, {
  headers: await csrfHeaders(page),
})
```

**不带的话 Django 一律返回 403**，于是：

- 期望 403 的那几行会「通过」，但**是因为错误的原因**
- 期望 204 的那几行会失败，报错指向权限，真实原因是 CSRF

> 📌 **这条规则是 `fe-v0.9.0` 写下的，`fe-v0.16.0` 自己又踩了一次：**
>
> > **一个鉴权测试如果因为请求根本没到达权限判断那一步而通过，
> > 它是假绿——比没有测试更糟，因为它给人安全感。**
>
> Vue 版直接复制正确版本。**但要理解为什么**，否则下次自己写 spec 时会再犯。

⚠️ 「无 CSRF 的写请求被拒」是**另一件事**，由 `bypass.spec.ts` 单独测。
**一条测试只测一件事**，否则你分不清它到底在测什么。

### 2. 🎯 第一节第 2 问：**不需要**

```ts
// React 版：需要在 e2e 构建里挂全局变量
await page.evaluate(() => window.__AUTH_STORE__.setState({ perms: ['*'] }))

// Vue 版：Pinia 的 state 本来就挂在 app 上
await page.evaluate(() => {
  const app = (document.querySelector('#app') as any).__vue_app__
  app.config.globalProperties.$pinia.state.value.auth.perms = ['*']
})
```

而且**改完立刻生效，不需要触发任何重渲染**（响应式自动传播）。

> 📌 **这个差异说明了什么**（[04 对比文档第 15 节](../04-React与Vue3做法对比.md#15-e2e一个字都不用改)）：
>
> React 版为了**演示**「前端权限可以被篡改」，专门加了一个 e2e-only 的全局变量，
> 还在 `store.ts` 里花了一整段注释解释「这不是为了测试而降低安全」。
>
> **Vue 版连那段解释都不需要。**
>
> 这不是 Vue 的安全缺陷——**两边的实际暴露程度完全一样**：
> React DevTools 同样能改任何组件状态，攻击者同样可以完全不用你的前端。
>
> Vue 只是**把「前端状态从来就不是秘密」这件事表达得更诚实**。

⚠️ 因此 Vue 版**可以不要 `--mode e2e` 这个构建变体**。少一个构建配置是好事——
但要在 `frontend-vue/CLAUDE.md` 里写明为什么两边不一样。

### 3. 第一节第 3 问：`reseedDatabase()`

```ts
test.beforeAll(reseedDatabase)
test.afterAll(reseedDatabase)
```

> ⚠️ 「直调 API」那一段真的会删掉工单，跑完必须还原——
> 否则下一个 spec 文件里的 80/50/5 就对不上了。

📌 `fe-v0.16.0` 踩过：`ticket-crud.spec.ts` 改了工单数量，
导致 `ticket-list.spec.ts` 随机变红。**症状是「E2E 不稳定」，原因是数据污染。**

⚠️ **不要**为了让测试变绿而把绝对断言（`共 50 条`）改成相对的——
那个数字必须等于后端的 `SCOPE_MATRIX`，**正是那条用例存在的理由**。

### 4. 第一节第 4 问：**生产构建**（`vite preview`）

```bash
npm run build && npx vite preview --port 5174
```

> ⚠️ dev server 每个请求都要现场转译模块，在小内存机器上会把整个套件拖垮——
> 表现是随机超时、每次红的用例都不一样，**极容易被误判成「E2E 就是不稳定」**
> 而加 retry 盖过去。
>
> 跑生产构建还有一个好处：**测的就是用户实际拿到的那份代码。**

📌 `fe-v0.16.0` 实测：9.6 分钟/8 个失败 → 1.7 分钟/48 个全绿。

### 5. 🔴 缓存必须是跨进程的

📌 `fe-v0.16.0` 踩过的第三个「E2E 不稳定」的原因：

> **LocMemCache 是每进程一份。** `seed_demo` 在自己的进程里 `bump_version()`，
> 而 `runserver` 那个进程完全看不到——于是 `cs_manager` 登录后菜单是空的、接口 403。

后端 `config/settings/dev.py` 已经改成 `FileBasedCache`。**Vue 版直接受益。**
但如果你另起了一套跑法，检查一次。

### 6. `message` 3 秒就消失：先断言它，再断言持久状态

```ts
// ✅
await expect(page.getByText('你的权限已更新')).toBeVisible()   // 先断言 toast
await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)  // 再断言持久态
```

反过来写的话，等你断言完按钮，toast 已经没了。

### 7. 按钮文案：「确定」不是「确 定」

如果 `vue-v0.2.0` 的 `auto-insert-space-in-button` 配对了，就是「确定」。

📌 `fe-v0.16.0` 在这里**反向**踩过一次：E2E 里写了 `确 定`，
而全局设置已经关掉了自动空格。

> **一条测试如果因为文案凑巧匹配而通过，它证明不了任何事。**

### 8. 🔴 必须有 `VUS-6`（换账号后的残留路由）

**这条是 Vue 独有的，React 版没有。**

```ts
test('换账号后不残留上一个账号的路由', async ({ page }) => {
  await login(page, 'superadmin')
  await page.goto('/system/users')
  await expect(page.getByRole('heading', { name: '用户管理' })).toBeVisible()

  await logout(page)
  await login(page, 'cs_staff')
  await page.goto('/system/users')

  // ⚠️ 期望 403 页面。
  //    没有 clearDynamicRoutes 的话，这里会进得去但一片空白 + 接口 403。
  await expect(page.getByText('403')).toBeVisible()
})
```

### 9. 🔴 矩阵常量对账（`tests/structural/matrixParity.test.ts`）

```ts
it('两个前端的 SCOPE_MATRIX 相同', async () => {
  const react = await import('../../../frontend/e2e/matrix.spec')  // 或读文件正则提取
  // ...
  expect(vueMatrix).toEqual(reactMatrix)
})
```

⚠️ 直接 import spec 文件会执行 Playwright 的 `test()`。
**改成读文件 + 正则提取常量块**更稳。

**为什么要这条**：改了后端行为要同步改两份 spec，漏改一份的表现是
「一个前端的 E2E 红了，另一个绿的」——而那时你会怀疑是那个前端有 bug。

---

## 四、必须覆盖的矩阵（与 React 版逐格相同）

```
            │ superadmin │ sysadmin │ cs_manager │ cs_staff │ no_role
────────────┼────────────┼──────────┼────────────┼──────────┼────────
菜单可见项   │    全部     │  系统管理 │  工单管理   │ 工单管理  │  空
/system/users│   200      │   200    │   403      │   403    │  403
工单列表条数 │    80      │    80    │    50      │    5     │  403
删除按钮     │    有       │    无    │    有      │    无     │  —
直调删除 API │   204      │   403    │   204      │   403    │  403
跨部门工单   │   200      │   200    │   404      │   404    │  403
```

**最后两行是关键**：「直调删除 API」绕过前端，验证后端独立成立。
它的期望值必须与「删除按钮」那一行**逻辑一致但独立成立**。

> 通过点按钮来测「后端拦不拦」是自欺欺人：**那测的还是前端。**

---

## 五、`bypass.spec.ts` 的四步

```
隐藏了 → 可以改回来 → 改回来也没用 → 连前端都不用
```

| 步 | 断言 |
| --- | --- |
| 1 | `cs_staff` 登录，删除按钮 `toHaveCount(0)` |
| 2 | 篡改 `$pinia.state.value.auth.perms = ['*']` → 按钮 `toBeVisible()` |
| 3 | 点下去 → 响应 **403** |
| 4 | `page.request.delete(...)`（完全绕过页面）→ **403** |

加上 httpOnly 的四条：

| # | 断言 |
| --- | --- |
| 1 | `document.cookie` **不含** `sessionid`，**含** `csrftoken` |
| 2 | `context().cookies()` 里 `sessionid.httpOnly === true` |
| 3 | XSS 偷不到会话，**但它仍然能直接发请求**（同源）→ 200 |
| 4 | 没有 CSRF token 的写请求 → 403 |

⚠️ 第 3 条的注释必须写清楚：

> **httpOnly 防的是「凭证被偷走异地复用」，不防「在受害者浏览器里以他的身份操作」。**
> 知道一个措施防的是什么，比知道它是个好措施重要。

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `bash scripts/e2e-vue.sh` | 全绿 |
| 2 | 矩阵的 6 行 × 5 列 | 逐格与表格一致 |
| 3 | `diff` 两边的 `matrix.spec.ts` | **只有端口和少数选择器不同** |
| 4 | `bypass.spec.ts` 四步 | 全绿 |
| 5 | httpOnly 四条 | 全绿 |
| 6 | 🔴 `VUS-6` 换账号残留路由 | 403 |
| 7 | `matrixParity` 结构性测试 | 绿 |
| 8 | 连跑两次 | 两次都绿（数据已 reseed） |
| 9 | 🔴 **React 版的 92 个 E2E** | **仍然全绿** |
| 10 | 后端 `pytest` / React 版单测 | 全绿 |

---

## 七、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `matrix.spec.ts` | 🟢 **断言逐字相同**（这是 `VAC-8`） |
| `reseed.ts` | 🟢 **逐字相同** |
| `helpers.ts` | 🟡 只改端口 |
| CSRF 头 | 🟢 **逐字相同**（同一个坑，同一个解法） |
| 生产构建跑 E2E | 🟢 **相同的理由** |
| 篡改 store 的方式 | 🔴 Vue **不需要专门的构建变体** |
| `VUS-6`（残留路由） | 🔴 **Vue 独有的一条测试** |
| 矩阵常量对账 | 🔴 **本阶段新增** |
| 少数 DOM 类名 | 🟡 antd 6 vs antdv 4 |

**本 tag 的结论**（也是整个阶段最重要的结论）：

> **一份能跨框架复用的 E2E，才是真正的规格说明书。**
>
> 越权矩阵在四种表现层（模板 / DRF / React / Vue）下**逐格相同**——
> 这证明它描述的是**系统的权限行为**，而权限行为不该因为前端换了框架而改变。
>
> 反过来：如果换个框架就有大量断言要跟着改，
> 那说明它测的是**实现**，不是**规格**。

---

## 八、延伸思考

1. `VAC-8` 把「断言逐字不变」列为**验收条件**而不是「省事的做法」。
   **这个转变意味着什么？** 如果某天真的需要改一条断言，你会怎么判断该不该改？

2. Vue 版少了一个构建变体（不需要 `--mode e2e`）。
   **这算简化吗？** React 版那段「这不是为了测试而降低安全」的长注释，
   在 Vue 版变成了什么？（提示：解释消失了，事实没变。）

3. `VUS-6` 是 Vue 独有的一条 E2E。
   **它测的是「Vue 的 bug」还是「我们代码的 bug」？**
   如果 `clearDynamicRoutes` 写对了，这条测试还有价值吗？

4. 现在同一套矩阵在四个地方跑：后端 pytest、React E2E、Vue E2E、（模板版的测试）。
   **这是重复劳动吗？** 每一处各自能发现什么别处发现不了的问题？
