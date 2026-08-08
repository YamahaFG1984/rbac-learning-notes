# vue-v0.7.0 — 按钮级权限，与 Vue 独有的「指令诱惑」

| 项 | 值 |
| --- | --- |
| 需求 | VE-4.1 ~ **VE-4.5** |
| 关键 V-ADR | [007](../02-设计文档.md)、[008](../02-设计文档.md) |
| 预计耗时 | 2.5 ~ 3 小时 |
| 变更规模 | ~180 行 |
| 上一个 tag | `vue-v0.6.0` |
| React 对应 | [`fe-v0.9.0`](../../frontend/tags/09-fe-v0.9.0-按钮级权限.md) |

> 🎯 **本 tag 是本阶段唯一一个「Vue 提供了 React 没有的选项，而我们选择不用它」的地方。**
> `VE-4.5` 要求你**先把指令方案写出来**，看清它的三个缺陷，再决定。

---

## 一、动手之前，先自己想清楚

1. `<Can>` 组件不传 `perm` 时，应该渲染还是不渲染？**为什么？**
2. antdv 的 `a-table` 的 `columns` 是**数据**不是模板。怎么按权限增删列？
3. Vue 可以写 `v-perm="PERM.X"` 指令。**它比 `<Can>` 好在哪、差在哪？**
4. 每加一个 `<Can>`，还必须同时做什么？（提示：安全红线第 2 条）

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/components/Can.vue` | 组件式权限 |
| 新建 | `src/auth/usePermission.ts`（补全） | `can` / `canAny` / `canAll` |
| 新建 | `src/directives/perm.ts` | ⚠️ **写出来是为了否定它**（`VE-4.5`） |
| 修改 | 各页面 | 受控按钮包 `<Can>` |
| 新建 | `docs/vue-frontend/notes/指令方案评估.md` | 评估记录 |

> ⚠️ `src/directives/perm.ts` **不注册到 app 上**，也不在任何页面使用。
> 它是一份「反面教材 + 可运行的证据」，`vue-v1.0.0` 之前保留，
> 在 `frontend-vue/CLAUDE.md` 里指向它。

---

## 三、接口契约

```ts
// Can.vue 的 props —— 与 React 版逐条对应
interface CanProps {
  perm?: PermCode     // ⚠️ 类型是 PermCode 不是 string
  anyOf?: PermCode[]
  allOf?: PermCode[]
}
// 插槽：默认插槽 = children；具名插槽 fallback = React 的 fallback prop
```

---

## 四、⚠️ 容易写错的地方

### 1. 第一节第 1 问：**不渲染**

```ts
const ok = computed(() =>
  props.perm ? can(props.perm)
  : props.anyOf ? props.anyOf.some(can)
  : props.allOf ? props.allOf.every(can)
  : false,        // ⚠️ 什么都不传 → false
)
```

「默认渲染」看起来更宽容，但它会让「写漏了 perm」**静默通过**——
这正是后端 `ADR-002`「默认拒绝」在前端的形态：
**让默认状态是安全的，写漏立刻可见。**

### 2. `<Can>` 内部**必须**调 `usePermission()`

不要在组件里重新写一遍 `perms.includes(...)`。
写两遍的话，将来加语法（比如「否定权限」）要改两处，而且**很可能只改一处**。

超管的 `['*']` 通配也只在那一个函数里处理，两个接口自动受益。

### 3. 第一节第 2 问：`columns` 用 `computed`

```ts
const { can } = usePermission()

const columns = computed(() => [
  ...BASE_COLUMNS,
  ...(can(PERM.TICKET_TICKET_UPDATE) ? [EDIT_COLUMN] : []),
])
```

⚠️ **必须是 `computed`。** 写成普通数组的话，`vue-v0.11.0` 权限变更后
列不会消失（[04 对比文档第 1 节](../04-React与Vue3做法对比.md)）。

**这就是为什么需要两个接口**（`F-ADR-009` / `V-ADR-007`）：
`columns` / `items` / `disabled` 这类是**数据**，包不进 `<Can>` 组件。

### 4. 🔴 第一节第 3 问：指令的三个缺陷

**先写出来。** 十几行，很快：

```ts
// src/directives/perm.ts
// ⚠️⚠️ 这份代码**不注册、不使用**。它是 VE-4.5 的证据。
export const vPerm: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    if (!auth.can(binding.value as PermCode)) {
      el.parentElement?.removeChild(el)
    }
  },
}
```

用它替换一个 `<Can>`，然后依次验证：

#### 缺陷 1：先渲染，再删除

指令的 `mounted` 在元素**已经挂载到 DOM 之后**执行。
实际行为是「渲染出来 → 发现没权限 → 删掉」。

**怎么看到**：给按钮加 `autofocus`，或者在 `onMounted` 里打个 log。
**副作用已经发生了。** `<Can>` 用 `v-if`，元素**根本不会被创建**。

#### 缺陷 2：🔴 删掉之后回不来（**致命**）

```
1. cs_manager 登录，有删除权限 → 按钮在
2. 管理员撤销他的删除权限
3. vue-v0.11.0 的版本号感知触发 → perms 更新
   ✅ <Can> 版：按钮消失
   ❌ 指令版：按钮消失（因为一开始就没渲染？不——它本来就在，现在也还在）
4. 管理员**恢复**权限
   ✅ <Can> 版：按钮回来
   ❌ 指令版：**永远不回来**，除非刷新页面
```

原因：被指令删掉的元素**已经不在虚拟 DOM 树上**，`updated` 钩子不会再被调用。

> 🔴 **这一条让 `VE-5.2` 在指令方案下无法实现。**
> 不是「难实现」，是**做不到**。

#### 缺陷 3：类型收窄失效

```vue
<a-button v-perm="'ticket:ticket:delet'">删除</a-button>   <!-- ✅ 编译通过 -->
```

指令值的类型是 `DirectiveBinding['value']`，即 `any`。

`F-ADR-012` 说过：

> TypeScript 在编译期挡住权限码 typo，
> **这是 SPA 相比模板版唯一在权限安全性上更强的地方。**

用了指令，**这个唯一的优势就原地退回去了**——退回到 Django 模板
`{% if 'ticket:ticket:delet' in perms %}` 的水平。

而 `<Can :perm="...">` 的 prop 类型是 `PermCode`，写错**编译不过**。

#### 记录下来

在 `docs/vue-frontend/notes/指令方案评估.md` 里写三条的**实测表现**，
不是复述本文档。写你自己看到的现象。

> 📌 **结论不是「指令不好」。**
> 指令是个好机制——`v-focus`、`v-resize`、`v-click-outside` 用它都很合适。
> 它们不参与条件渲染、不需要类型收窄、也不需要在状态变化后恢复。
>
> **「Vue 能做而 React 不能做的事」不等于「Vue 应该这么做」。**

### 5. 第一节第 4 问：**必须有对应的后端 `@require_perm`**

安全红线第 2 条：

> **模板隐藏按钮不是安全边界。每一个受控按钮，必须有对应的服务端校验。
> 成对出现，缺一不可。**

`vue-v0.13.0` 会加结构性测试自动对账（扫源码里的 `PERM.XXX` vs
`export_enforced_perms` 的输出）。现在先靠自觉，**但每加一个 `<Can>` 就去确认一次**。

### 6. `<Can>` 顶部的注释要写足

```vue
<!--
  ⚠️⚠️ 这是**体验优化，不是安全边界。**

     隐藏了「删除」按钮的用户**照样能删除**——
     perms 就在他的浏览器内存里，Vue Devtools 里改成 ['*'] 只需要几秒。
     ⚠️ 而且 Vue 版**连一个专门的调试口子都不需要**：
        Pinia 的 state 本来就是可写的响应式对象。

     > 模板版：攻击者不点你的按钮，他直接发请求。
     > SPA 版：他连你的前端都不用。

     唯一的安全边界是后端的 HasPerm + ScopedQuerysetMixin。
     vue-v0.14.0 会用 E2E 把这件事钉死。
-->
```

### 7. 权限码一律从常量引，禁止裸字符串

```vue
<!-- ✅ -->
<Can :perm="PERM.TICKET_TICKET_DELETE">
<!-- ❌ 写错静默不渲染，和模板版一样糟 -->
<Can perm="ticket:ticket:delet">
```

⚠️ 注意 `:perm`（绑定）和 `perm`（字面量字符串）的区别——
**写成 `perm="..."` 时类型检查形同虚设**，因为传的是字符串字面量，
TS 会去匹配联合类型；拼错的话**会报错**（这点还好），
但如果 prop 类型不小心写成了 `string`，就完全没有保护了。

---

## 五、卡住了看这里

<details>
<summary><b>提示：Can.vue</b></summary>

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { usePermission } from '@/auth/usePermission'
import type { PermCode } from '@/constants/permissions'

const props = defineProps<{
  perm?: PermCode
  anyOf?: PermCode[]
  allOf?: PermCode[]
}>()

const { can } = usePermission()

const ok = computed(() =>
  props.perm ? can(props.perm)
  : props.anyOf ? props.anyOf.some(can)
  : props.allOf ? props.allOf.every(can)
  : false,
)
</script>

<template>
  <slot v-if="ok" />
  <slot v-else name="fallback" />
</template>
```
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `cs_manager`（有删除权限） | 删除按钮**可见** |
| 2 | `cs_staff`（无删除权限） | 删除按钮**不可见** |
| 3 | `<Can>` 不传任何 prop | **不渲染** |
| 4 | 超管 | 全部按钮可见（`['*']` 通配生效） |
| 5 | `columns` 用 `computed` | `sysadmin` 看不到「操作」列 |
| 6 | 🎯 Devtools 把 `auth.perms` 改成 `['*']` | 按钮**立刻出现**（不需要刷新） |
| 7 | 🎯 接用例 6，点那个按钮 | 后端 **403** |
| 8 | 指令版的三个缺陷 | 都复现出来了，并记进 notes |
| 9 | 每个 `<Can>` 都有对应后端校验 | 逐个核对 |
| 10 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 6、7 是本 tag 的重点。** 用例 6 在 React 版需要
`VITE_EXPOSE_AUTH_STORE=1` 才能做，Vue 版**开着 Devtools 就行**。

---

## 七、和我的实现对比什么

```bash
# Can.tsx vs Can.vue —— 人肉对照
diff -u frontend/src/auth/usePermission.ts frontend-vue/src/auth/usePermission.ts
```

| 对比点 | 想一想 |
| --- | --- |
| 不传 prop 时渲染吗 | 渲染的话，写漏 `perm` 会静默放行 |
| `<Can>` 内部有没有重新实现判断 | 重新实现了的话，`['*']` 通配要处理两次 |
| `columns` 是 `computed` 吗 | 不是的话，`vue-v0.11.0` 的列不会消失 |
| 指令版真的写出来跑过吗 | 只读文档不写代码，缺陷 2 你不会有实感 |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `<Can>` 的接口 | 🟡 `<slot>` ← `children`；具名插槽 ← `fallback` prop |
| 默认拒绝 | 🟢 **决策相同** |
| 双接口（组件 + 函数） | 🟢 **决策相同**，理由逐字相同 |
| 通配处理一次 | 🟢 **决策相同** |
| `columns` 按权限增删 | 🔴 必须 `computed`（React 天然重算） |
| **`v-perm` 指令** | 🔴🔴 **Vue 独有的岔路，明确不走**（V-ADR-007） |
| 篡改演示 | 🔴 Vue **不需要专门开口子**（见 04 文档第 15 节） |
| 权限码类型收窄 | 🟢 两边都有；**但指令方案会把它丢掉** |

---

## 九、延伸思考

1. 指令的三个缺陷里，**只有第 2 条是致命的**（让 `VE-5.2` 无法实现）。
   如果本项目**不做**权限变更感知，指令方案还有什么问题？
   **这说明「某个方案好不好」依赖什么？**

2. 缺陷 3（类型丢失）能不能通过给指令加类型来解决？
   试着写 `Directive<HTMLElement, PermCode>`。**模板里的 `v-perm="'xxx'"` 会被检查吗？**
   （提示：`vue-tsc` 对指令值的检查程度。）自己验证一次，别猜。

3. 现在四层体验全部完成。用 `cs_staff` 登录，界面非常干净——
   **这份干净的安全价值是多少？**
   写下你的答案，`vue-v0.14.0` 之后回来对照。

4. `Can.vue` 的注释里说「Vue 版连一个专门的调试口子都不需要」。
   **这是 Vue 的安全缺陷吗？** 想清楚再回答——
   React DevTools 能不能改组件状态？攻击者需要用你的前端吗？
