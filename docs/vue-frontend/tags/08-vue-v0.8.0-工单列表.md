# vue-v0.8.0 — 工单列表（vue-query + 数据权限）

| 项 | 值 |
| --- | --- |
| 需求 | VE-6.1（列表部分） |
| 关键 V-ADR | [009](../02-设计文档.md)、[015](../02-设计文档.md) |
| 预计耗时 | 3 ~ 4 小时 |
| 变更规模 | ~300 行 |
| 上一个 tag | `vue-v0.7.0` |
| React 对应 | [`fe-v0.10.0`](../../frontend/tags/10-fe-v0.10.0-工单列表.md) |

---

## 一、动手之前，先自己想清楚

1. 分页和筛选条件存在哪？`ref`？Pinia？还是别的地方？
2. 后端返回 50 条，前端要不要再按权限筛一遍？
3. 🔴 `useQuery` 的 `queryKey` 里带筛选条件。**写成数组字面量会怎样？**
4. `cs_manager` 看到 50 条，`cs_staff` 看到 5 条。**前端要写任何代码来实现这个吗？**

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/api/tickets.ts` | 请求函数（**从 React 版复制**） |
| 新建 | `src/hooks/useTableQuery.ts` | 分页/筛选 ↔ URL |
| 新建 | `src/features/tickets/useTicketList.ts` | `useQuery` 封装 |
| 新建 | `src/features/tickets/TicketFilters.vue` | 筛选表单 |
| 重写 | `src/pages/tickets/List.vue` | 列表页 |

---

## 三、⚠️ 容易写错的地方

### 1. 第一节第 1 问：URL search params

| 数据 | 归属 |
| --- | --- |
| 工单列表 | 服务端状态 → **vue-query** |
| 分页、筛选 | 客户端状态，但属于**地址** → **URL search params** |
| 侧边栏折叠 | 纯 UI → Pinia `uiStore` |

理由与 React 版逐字相同：

> 刷新后筛选条件还在、链接可以分享给同事。用 `ref` 两条都做不到。

⚠️ **分享链接给同事时，他看到的是同样的筛选、不同的数据**——
数据权限在后端，URL 里带什么参数都改变不了他能看见的范围。
**这一点值得自己验证一次**（见自测用例 7）。

### 2. 🔴 第一节第 3 问：**静默失效**，列表纹丝不动

```ts
// ❌ 数组字面量在 <script setup> 里**只求值一次** → queryKey 定死
const { data } = useQuery({
  queryKey: ['tickets', params.value.page, params.value.status],
  queryFn: () => fetchTickets(params.value),
})

// ✅
const { data } = useQuery({
  queryKey: computed(() => ['tickets', params.value.page, params.value.status]),
  queryFn: () => fetchTickets(params.value),
})
```

**表现**：换页码、改筛选，表格纹丝不动。
**没有报错，没有警告，控制台干干净净。** 第一次加载还是对的。

**React 侧这个 bug 不可能存在**——组件函数每次重新执行，`queryKey` 每次重新求值。

> 🔴 [V-ADR-009](../02-设计文档.md)：**所有带参数的 `useQuery`，
> `queryKey` 一律写成 `computed(() => [...])`，即使当前没有参数会变。**
>
> 「现在没参数」会变成「以后加了参数」，而加参数的人不会想到还要改
> `queryKey` 的形式。统一写法把陷阱从「需要记住」变成「不可能踩到」。

**⚠️ 请故意写错一次，亲眼看到「改筛选没反应」。**
这是本 tag 最重要的一次体验（自测用例 8）。

### 3. 第一节第 2 问：**绝对不要**

```ts
// ❌ 看起来像多一道保险，实际是制造不一致的源头
const visible = computed(() => data.value?.results.filter((t) => canSee(t)))
```

- 分页会错乱：后端说 50 条，前端筛掉 10 条，分页器还显示 50
- 统计会对不上：列表显示 40，导出 50
- **零安全价值**——数据早就传到浏览器了，过滤发生在数据到达之后

`V-ADR-015` / `F-ADR-015`，与框架完全无关。
`vue-v0.13.0` 会加结构性测试扫源码守这条。

### 4. 第一节第 4 问：**一行都不用写**

数据权限的唯一执行点是后端的 `.for_user()`（`ADR-009`）。
前端只是把 API 返回的 `count` 显示出来。

```vue
<a-table :data-source="data?.results" :pagination="{ total: data?.count }" />
<div>共 {{ data?.count }} 条</div>
```

⚠️ `共 X 条` 这个文案 `vue-v0.14.0` 的 E2E 会断言，**必须与 React 版逐字相同**
（`共 {{count}} 条`，注意空格）。

### 5. `data` 在 script 里要 `.value`，模板里不用

```ts
// script
const total = computed(() => data.value?.count ?? 0)
```
```vue
<!-- 模板：自动 unref -->
<span>{{ data?.count }}</span>
```

⚠️ 这个不一致是 Vue 里最容易手滑的地方之一。好在**忘了 `.value` 会有类型错误**，
`vue-tsc` 能挡住。

### 6. `replace: true`——改筛选不该堆历史记录

```ts
router.replace({ query: { ...route.query, ...patch } })
```

不加的话改一次筛选就在历史里堆一条，用户按返回键要点十几次才能离开。
**这个坑与框架无关**，React 版注释里已经记过。

### 7. `route.query` 天生响应式，比 React 少一层

```ts
const route = useRoute()
const params = computed(() => parseParams(route.query, DEFAULTS))
```

不需要 `useSearchParams()` 的返回值、不需要 `useMemo`、不需要 `useCallback`。

🟡 [04 对比文档第 10 节](../04-React与Vue3做法对比.md#10-分页与筛选同步到-url)：
Vue 版这里明显更短（~20 行 vs ~30 行），因为「URL 是响应式数据源」在
Vue Router 里是内建的。

### 8. `enabled` 也可以是 `computed`

详情页要用到（`vue-v0.9.0`）：

```ts
useQuery({
  queryKey: computed(() => ['ticket', id.value]),
  queryFn: () => fetchTicket(id.value),
  enabled: computed(() => id.value != null),      // ⚠️ 同样要 computed
})
```

写成 `enabled: id.value != null` 会定死在初始值——同一个陷阱的另一个位置。

---

## 四、卡住了看这里

<details>
<summary><b>提示：useTableQuery</b></summary>

```ts
export function useTableQuery<T extends Record<string, string | number>>(defaults: T) {
  const route = useRoute()
  const router = useRouter()

  const params = computed(() => {
    const merged = { ...defaults }
    for (const key of Object.keys(defaults) as Array<keyof T & string>) {
      const raw = route.query[key]
      if (typeof raw !== 'string') continue
      merged[key] = (typeof defaults[key] === 'number'
        ? Number(raw) || defaults[key]
        : raw) as T[keyof T & string]
    }
    return merged
  })

  function setParams(patch: Partial<T>) {
    const next = { ...route.query }
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === '') delete next[k]
      else next[k] = String(v)
    }
    // ⚠️ replace 而不是 push
    router.replace({ query: next })
  }

  return { params, setParams }
}
```
</details>

---

## 五、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `superadmin` | **共 80 条** |
| 2 | `sysadmin` | **共 80 条** |
| 3 | `cs_manager` | **共 50 条** |
| 4 | `cs_staff` | **共 5 条** |
| 5 | 改筛选条件 | 列表**立刻重新请求**，URL 变化 |
| 6 | 改完筛选按 F5 | 条件还在 |
| 7 | 🎯 把带筛选的 URL 发给另一个角色的账号打开 | 筛选相同，**条数不同** |
| 8 | 🔴 故意把 `queryKey` 写成数组字面量 | 改筛选**没反应，且不报错**（看一次，再改回来） |
| 9 | 改筛选后按返回键 | 一次就离开页面（不堆历史） |
| 10 | 网络面板 | 切分页**不重复请求 profile**（`VNFR-7`） |
| 11 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ 用例 1~4 的数字必须与后端 `tests/test_permission_matrix.py` 的
`SCOPE_MATRIX` 完全一致，也与 React 版一致。**对不上就是有一层多做了事。**

---

## 六、和我的实现对比什么

```bash
diff -u frontend/src/api/tickets.ts frontend-vue/src/api/tickets.ts   # 期望：几乎无差异
diff -u frontend/src/hooks/useTableQuery.ts frontend-vue/src/hooks/useTableQuery.ts
```

| 对比点 | 想一想 |
| --- | --- |
| `queryKey` 是不是 `computed` | 跑用例 8 |
| 分页存在哪 | 存 `ref` 的话用例 6、7 会红 |
| 有没有对列表二次过滤 | 过滤了的话用例 1~4 的数字会对不上 |
| `useTableQuery` 比 React 版短多少 | 短的那部分来自哪个能力？ |

---

## 七、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `api/tickets.ts` | 🟢 **逐字相同** |
| `useTableQuery` | 🟡 Vue 更短（`route.query` 天生响应式） |
| **`queryKey`** | 🔴🔴 **必须 `computed`，写错静默失效** |
| `enabled` 等选项 | 🔴 同样要 `computed` |
| 返回值 | 🟡 `Ref`（script 里 `.value`，模板自动 unref） |
| 不做二次过滤 | 🟢 **决策相同**，与框架无关 |
| 断言数字 | 🟢 **80 / 50 / 5，逐字相同** |
| `replace: true` | 🟢 同一个坑，与框架无关 |

**本 tag 的结论**：数据层几乎完全复用，唯一的实质差异是
`queryKey` 的响应式要求——而它恰好是本阶段**最容易踩且最不报错**的一个坑。

---

## 八、延伸思考

1. `@tanstack/react-query` 和 `@tanstack/vue-query` 是同一个 core 的两个适配层，
   版本号都是 `5.101.4`。它们各自留了一个**静默失效点**：
   - React：v5 移除了 `useQuery` 的 `onSuccess`
   - Vue：`queryKey` 必须是响应式的

   **这两个失效点有共同点吗？**（提示：它们都在「适配层必须适配、又无法统一」的接缝上。）

2. 用例 7 是数据权限的现场演示。**在 Django 模板版里怎么做同样的演示？**
   哪个更有说服力？

3. `useTableQuery` 在 Vue 里更短。**短的那 10 行原本在做什么？**
   它们消失了，是因为 Vue 更强，还是因为这个能力被挪到了别的地方？
