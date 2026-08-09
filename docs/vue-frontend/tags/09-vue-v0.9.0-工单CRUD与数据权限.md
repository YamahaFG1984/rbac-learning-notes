# vue-v0.9.0 — 工单 CRUD 与数据权限的前端表现

| 项 | 值 |
| --- | --- |
| 需求 | VE-6.1、VE-7.3 |
| 关键 V-ADR | — |
| 预计耗时 | 3 ~ 4 小时 |
| 变更规模 | ~350 行 |
| 上一个 tag | `vue-v0.8.0` |
| React 对应 | [`fe-v0.11.0`](../../frontend/tags/11-fe-v0.11.0-工单CRUD与数据权限.md) |

---

## 一、动手之前，先自己想清楚

1. 用户拿到一个不属于自己数据范围的工单 ID，直接访问 `/tickets/42`。
   后端返回什么？前端该显示什么？
2. 删除成功后，列表怎么刷新？手动重新请求，还是有别的办法？
3. 后端表单校验失败返回 `{"title": ["这个字段是必填项"]}`，怎么映射到表单？
4. 「派单」是页面级操作还是行级操作？下拉框里应该出现哪些用户？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/pages/tickets/Detail.vue` | 详情 |
| 新建 | `src/features/tickets/TicketForm.vue` | 新建/编辑弹窗 |
| 新建 | `src/features/tickets/AssignModal.vue` | 派单 |
| 新建 | `src/features/tickets/useTicketMutations.ts` | 增删改 + 失效 |
| 新建 | `src/utils/formErrors.ts` | 后端字段错误 → 表单（**逻辑同 React 版**） |
| 新建 | `src/components/ResourceNotFound.vue` | 「不存在或你无权访问」 |
| 修改 | `src/pages/tickets/List.vue` | 行操作列 |

---

## 三、⚠️ 容易写错的地方

### 1. 第一节第 1 问：后端 **404**，前端「不存在或你无权访问」

后端 `ADR-009`：**数据权限范围外返回 404 而不是 403**，避免泄露记录存在性。

```vue
<ResourceNotFound v-if="isNotFound" />
```

⚠️ 文案统一为「**工单不存在或你无权访问**」，两种情况都覆盖，**且不泄露哪一种**。

⚠️ 这条要**明确写在注释里**，否则后来者会把 404 当成「接口路径写错了」去排查路由。

⚠️ 文案 `vue-v0.14.0` 的 E2E 会断言，**必须与 React 版逐字相同**。

### 2. 第一节第 2 问：`invalidateQueries`

```ts
const queryClient = useQueryClient()

const { mutate: remove } = useMutation({
  mutationFn: deleteTicket,
  onSuccess: () => {
    // ⚠️ 不要手动 refetch，也不要手动改本地数组
    queryClient.invalidateQueries({ queryKey: ['tickets'] })
  },
})
```

⚠️ **`useMutation` 的 `onSuccess` 在 v5 里仍然存在**（被移除的是 `useQuery` 的）。
两个适配层在这一点上完全一致。

❌ 反例：`data.value.results.splice(i, 1)` —— 手改本地数据会让 `count`、
分页、统计全部对不上，而且下次 refetch 又变回来。

### 3. 第一节第 3 问：`formErrors.ts`，逻辑与 React 版相同

```ts
// 后端：{"title": ["这个字段是必填项"], "detail": "..."}
export function applyServerFieldErrors(err: unknown, setFieldError: (f: string, m: string) => void) {
  const data = (err as AxiosError<Record<string, string[]>>)?.response?.data
  if (!data || typeof data !== 'object') return false
  let matched = false
  for (const [field, msgs] of Object.entries(data)) {
    if (field === 'detail' || !Array.isArray(msgs)) continue
    setFieldError(field, msgs[0])
    matched = true
  }
  return matched          // ⚠️ 返回是否命中，没命中就走通用提示
}
```

⚠️ 返回值不能少——后端也可能返回 `{"detail": "..."}`（非字段错误），
那时要走 `message.error(detail)` 而不是静默什么都不做。

🟡 与 React 版的差异只在最后一步：antdv 的表单错误要通过
`formRef.value.validateFields` 的 `rules` 或手动维护 `errorState`，
没有 antd 的 `form.setFields()` 那么直接。

### 4. 🔴 第一节第 4 问：**行级**，且下拉框里**不能是全部用户**

**派单是针对某一条工单的**（`/tickets/<pk>/assign/`），
所以按钮在**行操作列**里，不在页面工具栏。

> 📌 `fe-v0.9.0` 在这里犯过一个建模错误：把派单放进了页面工具栏，
> `fe-v0.10.0` 才移到行操作列，导致 `fe-v0.9.0` 的 E2E 变红。
> **Vue 版直接写对**——这是「已经走过一遍」的好处之一。

**下拉框的数据来源**：`GET /api/v1/tickets/assignable_users/`，
**不是** `GET /api/v1/users/`。

> 🔴 `fe-v0.11.0` 在这里发现了一个**真实漏洞**：
> 派单下拉框列出了**全部 6 个用户**，而 `cs_manager` 没有 `system:user:view` 权限，
> 却能看到完整的员工名单。
>
> 后端已经修好了（`apps/tickets/services.py::get_assignable_users`，
> 走 `get_user_dept_ids()`，ADR-016）。
> **Vue 版直接用那个接口就行**——这是从「接第二个前端」里赚到的第二笔红利。

⚠️ 但仍然要验证一次（自测用例 6）。**别因为「后端修过了」就假定前端调对了接口。**

### 5. 删除确认弹窗的按钮文案

```ts
Modal.confirm({ title: '确认删除？', okText: '确定', cancelText: '取消' })
```

⚠️ 如果 `vue-v0.2.0` 的 `auto-insert-space-in-button` 配对了，
这里就是「确定」；配错的话是「确 定」。

> 📌 `fe-v0.16.0` 在这里正反都踩过一次：E2E 里写了 `确 定`，
> 而全局设置已经关掉了自动空格。**一条测试如果因为文案凑巧匹配而通过，
> 它证明不了任何事。**

### 6. `<Can>` 与后端校验成对

行操作列里每个按钮：

| 按钮 | 前端 | 后端 |
| --- | --- | --- |
| 编辑 | `<Can :perm="PERM.TICKET_TICKET_UPDATE">` | `perm_map['update']` |
| 删除 | `<Can :perm="PERM.TICKET_TICKET_DELETE">` | `perm_map['destroy']` |
| 派单 | `<Can :perm="PERM.TICKET_TICKET_ASSIGN">` | `@action assign` |
| 导出 | `<Can :perm="PERM.TICKET_TICKET_EXPORT">` | `@action export` |

**缺一不可。** `vue-v0.13.0` 的结构性测试会自动对账。

### 7. 表单字段用白名单

后端安全红线第 3、4 条在前端的延伸：

- 表单里**只出现**你打算让用户改的字段
- **`is_superuser` 永不出现在任何表单里**

⚠️ 这两条**由后端序列化器保证**，前端写什么都改变不了。
但前端也不该显示一个提交上去会被忽略的字段——那是误导。

### 8. 导出：不要用 axios 拿 blob 再手动下载

```ts
// ✅ 直接跳转，让浏览器处理 Content-Disposition
window.location.href = '/api/v1/tickets/export/?' + new URLSearchParams(params).toString()
```

⚠️ 但这样就绕过了 axios 拦截器——**403 时用户会看到一个下载失败的空文件**
而不是提示。

**取舍**：本项目接受这个瑕疵（与 React 版一致），因为 `<Can>` 已经隐藏了
无权限用户的导出按钮，而真正越权的人本来就该看到失败。
**记在已知简化里，不要假装它不存在。**

---

## 四、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `cs_manager` 新建工单 | 成功，列表 51 条 |
| 2 | 删除 | 列表自动刷新，条数减 1 |
| 3 | 🎯 `cs_manager` 访问技术部工单的 ID | **「不存在或你无权访问」**，不是 403，页面不崩 |
| 4 | 标题留空提交 | 表单**字段下方**显示后端的错误文案 |
| 5 | 后端返回 `{"detail": "..."}` | 走通用提示，不静默 |
| 6 | 🔴 `cs_manager` 打开派单下拉框 | **只有他范围内的用户**，不是全部 6 个 |
| 7 | `cs_staff` 看行操作列 | **没有删除按钮** |
| 8 | 删除确认弹窗 | 按钮是「确定」不是「确 定」 |
| 9 | 详情页刷新 | 正常（不是 404） |
| 10 | 导出 | 下载 CSV，内容条数 == 列表条数 |
| 11 | 后端 `pytest` / React 版单测 | 全绿 |

---

## 五、和我的实现对比什么

```bash
diff -u frontend/src/utils/formErrors.ts frontend-vue/src/utils/formErrors.ts
git diff vue-v0.8.0 vue-v0.9.0 -- frontend-vue/
```

| 对比点 | 想一想 |
| --- | --- |
| 派单在行里还是工具栏 | 在工具栏的话，「派给谁」这个问题怎么回答？ |
| 派单下拉框调的哪个接口 | 调 `/users/` 的话跑用例 6 |
| 删除后怎么刷新列表 | 手改本地数组的话，`count` 对得上吗？ |
| 404 文案泄露信息吗 | 「你无权访问」和「不存在」分开写就泄露了 |

---

## 六、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `api/tickets.ts` | 🟢🟢 **去掉注释后与 React 版逐字相同**（实测 diff 为空） |
| `useMutation` + `invalidateQueries` | 🟢 **逐字相同**（`onSuccess` 两边都在） |
| `formErrors.ts` 的**解析**逻辑 | 🟢 相同（DRF 错误体、区分 `detail` 与字段错误） |
| 表单错误回填的**最后一步** | 🟡 antdv 没有 `form.setFields()`，要自己驱动 `:help` / `:validate-status` |
| 表单绑值 | 🟡 `v-model:value` ← 受控组件 |
| **`Select` 不接受 `null`** | 🔴 后端的 `assignee` 是 `number \| null`，antdv 只吃 `undefined`，要在边界转一次 |
| 404 语义与文案 | 🟢 **逐字相同** |
| 派单接口 | 🟢 **相同**（后端红利，实测确认只返回范围内的人） |
| 导出的取舍 | 🟢 **相同的已知瑕疵** |
| `<Can>` 与后端成对 | 🟢 **相同的硬规则** |
| **`<App>` + `App.useApp()`** | 🔴📌 **实测踩到，但这是我没照抄到位，不是框架差异**（见下） |

### 🔴📌 `Modal.confirm()` 的按钮渲染成「确 定」（实测）

直接 `import { Modal } from 'ant-design-vue'` 然后 `Modal.confirm(...)`，
按钮文本实测是：

```
["取 消", "确 定"]        ← 静态方法
["派单", "删除"]          ← 同一页面里树内的按钮，正常
```

**原因**：`Modal.confirm()` / `message.*` 这类**静态方法**在组件树**之外**
渲染（挂到 body 的独立 vnode 树），因此**拿不到 `<ConfigProvider>` 的配置**——
`auto-insert-space-in-button="false"` 对它完全无效。

后果是所有按文本找确认框按钮的代码（含 E2E）全部失效，
而报错只说「找不到元素」。

**修法**：`<App>` 包一层，调用方用 `App.useApp()` 拿 context 感知的
`modal` / `message` / `notification`。

> 🟢 **React 版早就这么做了**——`main.tsx` 里有 `<AntdApp>`，
> 页面里用 `App.useApp()`。antd 5 引入 `<App>` 正是为了这个。
>
> ⚠️ **所以这一条不是「Vue 的坑」，是我没照抄到位。**
> 值得记下来的原因恰恰在这里：**我一路在对照 React 版，
> 仍然漏掉了一个它早就解决的问题**——因为那个解法藏在
> `main.tsx` 的一层组件包装里，不在我正在抄的那个文件里。
>
> 「照着另一个实现写」比「从零写」少踩很多坑，
> **但它会漏掉那些「不在你视线范围内的文件」里的决策。**

### 📌 派单候选人：后端红利的实测确认

`fe-v0.11.0` 挖出的真实漏洞（下拉框列出全部 6 个用户），后端已修。
Vue 版实测：

```
cs_manager 的派单候选人：3 人
  王主管（客服部） / 李专员（客服一组） / 新人（客服一组）
  ← 不含技术部的人
```

**直接受益，一行没写。** 但仍然验证了一次——
别因为「后端修过了」就假定前端调对了接口。

**本 tag 的结论**：业务 CRUD 层几乎没有框架差异。
需要重写的只有两处，**都是 UI 库能力的差异，不是 Vue/React 的差异**：
表单错误怎么显示、`Select` 的空值类型。

---

## 七、延伸思考

1. `fe-v0.11.0` 挖出了「派单下拉框泄露全部用户」这个真实漏洞。
   **Vue 版一开始就没有这个问题**，因为后端已经修好了。
   **那么：如果当初没有做 React 版，这个漏洞会被发现吗？**
   接第二个前端的价值，有多少在前端、有多少在「逼你重看后端」？

2. 用例 3 是数据权限在前端的表现。**在 Django 模板版里，同样的操作是什么体验？**
   两者哪个更容易让用户误以为「链接失效了」？

3. 导出接口绕过了 axios 拦截器，这是个已知瑕疵。
   **有没有既保留浏览器原生下载、又能走拦截器的做法？** 代价是什么？
