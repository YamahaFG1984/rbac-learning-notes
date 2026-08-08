# vue-v0.4.0 — 🔴 Pinia 权限 Store 与「组件外访问」

| 项 | 值 |
| --- | --- |
| 需求 | VE-2.1 ~ **VE-2.6** |
| 关键 V-ADR | [003](../02-设计文档.md)、[006](../02-设计文档.md) |
| 预计耗时 | 2.5 ~ 3 小时 |
| 变更规模 | ~250 行 |
| 上一个 tag | `vue-v0.3.0` |
| React 对应 | [`fe-v0.6.0`](../../frontend/tags/06-fe-v0.6.0-权限Store.md) |

> ⚠️ React 阶段这一步的前面还有一个 `fe-v0.5.0`（后端加 `route_path` / `component`
> 字段 + 导出权限常量）。**本阶段那部分只剩一件事：给导出命令加 `--out`。**
> 见第三节。

---

## 一、动手之前，先自己想清楚

1. profile 拉回来之后写进 store。**谁有资格写？** 允许几个入口？
2. `perms` 是 `string[]`。组件里读它，需要做什么才能保证权限变更时会更新？
3. 🔴 `api/client.ts` 的拦截器里要读 store。**直接 `import { useAuthStore }` 然后在模块顶层调，会发生什么？**
4. profile 请求**失败**时，`status` 该是什么？如果保持 `'unknown'` 会怎样？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 修改 | `src/auth/store.ts` | 加 `can()`（`perms` / `menus` / `knownRoutes` 在 `vue-v0.2.0` 已就位，见那份规格书的「两处与初稿不同」） |
| 新建 | `src/auth/useProfileQuery.ts` | vue-query 拉 profile → 写 store |
| 新建 | `src/auth/usePermission.ts` | 唯一的权限判断函数 |
| 新建 | `src/types/auth.ts` | `Profile` / `MenuNode` / `User` |
| 生成 | `src/constants/permissions.ts` | ⚙️ **后端生成，禁止手写** |
| 修改 | `apps/rbac/management/commands/export_perm_constants.py` | 加 `--out` |
| 修改 | `apps/rbac/management/commands/export_enforced_perms.py` | 加 `--out` |
| 修改 | `src/main.ts` | 注册 VueQueryPlugin |

---

## 三、唯一的后端改动（VBE-1）

```python
def add_arguments(self, parser):
    parser.add_argument("--check", action="store_true", ...)
    parser.add_argument(
        "--out",
        default="frontend/src/constants/permissions.ts",
        # ⚠️ 默认值必须保持原样。
        #    React 版的 CI 和 frontend/CLAUDE.md 都写着无参数调用，
        #    改默认值会让**上一个阶段的 CI 变红**（VAC-10）。
        help="输出路径（相对 BASE_DIR）",
    )
```

```bash
python manage.py export_perm_constants                                          # React
python manage.py export_perm_constants --out frontend-vue/src/constants/permissions.ts
```

> 📌 **这就是 `F-ADR-008` 预判过的摩擦，但位置猜错了。**
>
> 当初的原话是「如果哪天要支持第三个前端，**这张表**会开始打架」。
> 实际打架的不是 `Permission` 表——`route_path` / `component`
> 一个字都不用改，因为 Vue 用了和 React 完全相同的组件命名
> （`tickets/List` → `pages/tickets/List.vue`）。
>
> 打架的是**导出命令的硬编码路径**。
> **预判对了方向，猜错了位置。** 这条记录比「预判成功」有价值。

---

## 四、⚠️ 容易写错的地方

### 1. 第一节第 1 问：**只有一个写入口**

```ts
// ✅ 只有 useProfileQuery 能调 setProfile
// ❌ 组件里、守卫里、拦截器里都不许调
```

理由与 React 版逐字相同（`F-ADR-005`）：**两处写入 = 两个真相源，很快就会不一致。**

⚠️ Pinia 让这条**更难守**：store 的 state 是公开可写的
（`auth.perms = [...]` 完全合法，不报错）。Zustand 至少要走 `setState`。

→ 对策：在 store 顶部写明约束，并在 `vue-v0.13.0` 加一条结构性测试，
扫描 `auth.perms =` / `auth.menus =` 这类直接赋值。

### 2. 第一节第 2 问：`storeToRefs` 或者直接用 `auth.perms`

```ts
// ❌ 解构 → 丢响应性 → 权限变更后**永远不更新**
const { perms } = useAuthStore()

// ✅ 两种都行
const auth = useAuthStore()          // 之后一直用 auth.perms
const { perms } = storeToRefs(useAuthStore())   // perms 是 Ref
```

**这个 bug 在本 tag 不会暴露**——perms 拉回来一次就不变了。
它要到 `vue-v0.11.0`（权限变更感知）才炸。

> 🔴 [04 对比文档第 2 节](../04-React与Vue3做法对比.md#2-权限-store-zustand--pinia)：
> React 忘了写 selector 是**性能问题**，Vue 忘了 `storeToRefs` 是**正确性问题**。
> 这是两边失误方向相反的第一个现场。

⚠️ 更坑的是：模板里写 `auth.perms` 是**对的**（模板里的属性访问天然被追踪），
只有在 `<script setup>` 里解构才有问题。所以「把模板表达式抽成变量」
这个最常见的重构动作，会**引入 bug**。

### 3. 🔴 第一节第 3 问：会抛错。这是 `VE-2.6`

```ts
// ❌ src/api/client.ts 模块顶层
import { useAuthStore } from '@/auth/store'
const auth = useAuthStore()
// getActivePinia() was called with no active Pinia. Did you forget to install pinia?
```

`client.ts` 在 `main.ts` 里被 import，而那时 `app.use(pinia)` 还没执行。

**解法（[V-ADR-003](../02-设计文档.md)）**：

```ts
// ✅ 挪进函数体
client.interceptors.request.use((config) => {
  // ⚠️ useAuthStore() **必须**写在这里，不能提到模块顶层。
  //    本文件在 main.ts 里被 import，那时 app.use(pinia) 还没跑。
  //    提到顶层的表现是应用白屏，报错说「忘了装 pinia」——
  //    而实际是**调用时机**问题。
  const auth = useAuthStore()
  ...
})
```

需要触发副作用（跳登录页、invalidate）的，用**注入**，形状与 React 版完全相同：

```ts
let onUnauthenticated: (() => void) | null = null
export function setUnauthenticatedHandler(h: () => void) { onUnauthenticated = h }
```

> 📌 **同一个做法，两边的理由不同。**
> React 用注入是因为**依赖方向**（`api/` 不许 import 路由和 QueryClient）；
> Vue 多一条：**实例化时序**。
>
> 这说明「注入」不是某个框架的技巧，而是
> **「模块加载期 ≠ 应用运行期」这个普遍问题的通解**。

### 4. 🔴 第一节第 4 问：**必须置成终态**，否则 `vue-v0.5.0` 会无限重定向

```ts
async function fetchProfileIntoStore() {
  try {
    const profile = await fetchProfile()
    auth.setProfile(profile)          // status → 'authenticated'
  } catch (e) {
    auth.reset()                      // ⚠️ status → 'anonymous'，**不能留在 unknown**
    throw e
  }
}
```

**保持 `'unknown'` 的后果**（下个 tag 才会炸）：

```
守卫看到 status === 'unknown' → 拉 profile → 失败 → status 还是 unknown
  → return { ...to } 重新导航 → 守卫又看到 unknown → 无限循环
  → Vue Router 抛 Maximum recursive navigation guard calls
```

⚠️ **现在就写对。** 这个 bug 到下个 tag 才出现，但根因在这里。

### 5. `useQuery` 的 `queryKey`——profile 没参数，但也写 `computed`

```ts
useQuery({
  queryKey: computed(() => ['profile']),   // 没参数也写 computed（V-ADR-009）
  queryFn: fetchProfile,
  staleTime: Infinity,
  refetchOnWindowFocus: false,
  retry: false,
})
```

**为什么没参数也要写**：「现在没参数」会变成「以后加了参数」，
而加参数的人不会想到还要改 `queryKey` 的形式。
统一写法把陷阱从「需要记住」变成「不可能踩到」。

⚠️ `staleTime: Infinity` + `refetchOnWindowFocus: false` + `retry: false`
三个选项与 React 版逐字相同，理由也相同：

> profile 不该被「窗口聚焦」「网络重连」这类事件随意刷新。
> 它只应由两件事触发重拉：版本号变化和收到 403。

### 6. Query → store 的同步用 `watch`

```ts
const { data } = useQuery({ ... })

watch(data, (profile) => {
  if (profile) auth.setProfile(profile)
}, { immediate: true })
```

⚠️ `immediate: true` 不能少——缓存命中时 `data` 一开始就有值，
不加的话 `watch` 不会触发，store 永远是空的。

> 📌 React 版这里用的是 `useEffect`，而 `fe-v0.13.0` 在这上面踩过一个坑
> （`await refetchQueries()` 之后 store 还没更新）。
> **`watch` 有没有同样的窗口？** 到 `vue-v0.11.0` 实测，
> 回填 [04 对比文档第 11 节](../04-React与Vue3做法对比.md#11-把-query-的结果写进-store一个跨框架的时序陷阱)。

### 7. 通配 `'*'` 只处理一次

```ts
// store 里唯一一处
const can = (code: PermCode) => perms.value.includes('*') || perms.value.includes(code)
```

`<Can>`、守卫、菜单全部调它。写两遍的话，将来加语法要改两处，而且很可能只改一处。
**这条与框架完全无关**（`F-ADR-009`，后端安全红线第 5 条的前端形态）。

---

## 五、卡住了看这里

<details>
<summary><b>提示：store</b></summary>

```ts
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const perms = ref<string[]>([])
  const menus = ref<MenuNode[]>([])
  const knownRoutes = ref<string[]>([])
  const status = ref<'unknown' | 'authenticated' | 'anonymous'>('unknown')

  const can = (code: PermCode) =>
    perms.value.includes('*') || perms.value.includes(code)

  function setProfile(p: Profile) {
    user.value = p.user
    perms.value = p.perms
    menus.value = p.menus
    knownRoutes.value = p.knownRoutes
    status.value = 'authenticated'
  }

  function reset() {
    user.value = null
    perms.value = []
    menus.value = []
    knownRoutes.value = []
    status.value = 'anonymous'      // ⚠️ 终态，不是 'unknown'
  }

  return { user, perms, menus, knownRoutes, status, can, setProfile, reset }
})
```
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 登录后 | store 里有 user / perms / menus |
| 2 | 超管登录 | `perms === ['*']`，`can(任意码)` 为 true |
| 3 | `no_role` 登录 | `perms === []`，`menus === []` |
| 4 | 拦截器里 `console.log(useAuthStore().perms)` | **不报错**，能打出来 |
| 5 | 🔴 把 `useAuthStore()` 提到 `client.ts` 顶层 | **白屏 + 报错**（做一次，看清报错长什么样，再改回来） |
| 6 | profile 接口断网 | `status === 'anonymous'`，**不是 unknown** |
| 7 | `permissions.ts` | 由命令生成，**22 个权限码**（⚠️ 权限点树有 26 个节点，其中 4 个是无 `code` 的 `catalog` 容器） |
| 8 | `diff frontend/src/constants/permissions.ts frontend-vue/src/constants/permissions.ts` | **完全相同** |
| 9 | `python manage.py export_perm_constants --check`（无参数） | 通过（**没弄坏 React 版**） |
| 10 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 5 请务必做一次。** 亲眼看过那个报错，将来在别的项目里再遇到，
你会在三秒内认出它——而不是去怀疑「是不是 pinia 没装好」。

---

## 七、和我的实现对比什么

```bash
diff -u frontend/src/auth/usePermission.ts frontend-vue/src/auth/usePermission.ts
diff -u frontend/src/constants/permissions.ts frontend-vue/src/constants/permissions.ts   # 必须为空
```

| 对比点 | 想一想 |
| --- | --- |
| `setProfile` 有几个调用点 | 超过一个就是两个真相源 |
| 有没有在 script 里解构 store | 现在不炸，`vue-v0.11.0` 会炸 |
| `client.ts` 里 `useAuthStore()` 在哪一层 | 顶层的话现在就炸 |
| profile 失败后 `status` 是什么 | 是 `unknown` 的话，下个 tag 会无限重定向 |
| `--out` 的默认值改了吗 | 改了的话用例 9 会红 |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| store 定义 | 🔴 `defineStore` + `ref` ← `create` + `set` |
| 组件里读 | 🔴 `storeToRefs` / 直接 `auth.x` ← selector 函数 |
| **组件外读** | 🔴🔴 **Vue 独有的时序问题**（`VE-2.6` / `V-ADR-003`） |
| 忘了细化订阅/解构 | 🔴 **失误方向相反**：React 是性能，Vue 是正确性 |
| 权限判断函数 | 🟡 同构；Vue 不需要 `useCallback` |
| `queryKey` | 🔴 必须 `computed`（`V-ADR-009`） |
| Query → store | 🟡 `watch` ← `useEffect`（**时序是否等价待验证**） |
| 三态 status | 🟢 决策相同，Vue 多一条独立理由 |
| 权限常量文件 | 🟢 **内容逐字节相同**（同一个生成器） |
| 后端改动 | 🟡 ~20 行（React 阶段是整整一个 tag） |

**本 tag 是本阶段差异最集中的地方之一**——[04 对比文档](../04-React与Vue3做法对比.md)
总账里「真正 Vue 特有的 6 条决策」，有 3 条在这个 tag 里
（003 store 时序、009 queryKey、011 测试隔离的前置条件）。

---

## 九、延伸思考

1. Pinia 的「store 绑在 app 实例上」带来了 `VE-2.6` 这个麻烦。
   **它换来了什么？**（提示：想想 SSR 下 Zustand 的模块级单例会发生什么。）
   本项目不做 SSR，所以**只付了代价没拿到收益**——
   这种情况在技术选型里常见吗？怎么识别？

2. 用例 8 要求两个前端的常量文件**逐字节相同**。
   如果哪天不同了，可能是什么原因？**哪一种最危险？**

3. `setProfile` 是唯一写入口这条规则，在 Zustand 下靠「必须走 `setState`」
   有一半的机械保障，在 Pinia 下**完全没有**。
   除了写注释和加结构性测试，还有别的办法吗？
   （提示：`readonly()` 能做什么、代价是什么。）
