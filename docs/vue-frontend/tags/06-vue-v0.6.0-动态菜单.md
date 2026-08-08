# vue-v0.6.0 — 动态菜单

| 项 | 值 |
| --- | --- |
| 需求 | VE-3.3、VE-3.4、VE-3.5 |
| 关键 V-ADR | — |
| 预计耗时 | 1.5 ~ 2 小时 |
| 变更规模 | ~120 行 |
| 上一个 tag | `vue-v0.5.0` |
| React 对应 | [`fe-v0.8.0`](../../frontend/tags/08-fe-v0.8.0-动态菜单.md) |

> 本 tag 的 diff 应该很干净——布局在 `vue-v0.3.0` 就做完了。
> 对照后端 `v0.11.0`（侧边栏模板仅 30 行变化）和 `fe-v0.8.0`。

---

## 一、动手之前，先自己想清楚

1. 后端的 `menus` 已经**过滤好了**（空目录不返回、无权限的不返回）。
   前端还需要再判断一次权限吗？
2. `MenuNode` 是 `{id, name, icon, routePath, children}`，
   antdv `a-menu` 要的是 `{key, icon, label, children}`。**这个转换放在哪？**
3. 在 `/tickets/42`（详情页）时，`/tickets` 这个菜单项应该高亮吗？
4. 用户手动折叠了某个父目录，下一次导航时该把它强制展开回去吗？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 重写 | `src/layouts/Sidebar.vue` | 由 `auth.menus` 渲染，**删掉写死的常量** |
| 新建 | `src/layouts/menuAdapter.ts` | `MenuNode[]` → antdv items（**纯函数**） |
| 新建 | `src/layouts/iconMap.ts` | 图标名 → 组件 |

---

## 三、接口契约

**与 React 版逐字相同**：

```ts
export function toMenuItems(menus: MenuNode[]): ItemType[]
export function findActiveKeys(menus: MenuNode[], pathname: string): {
  selectedKeys: string[]
  openKeys: string[]
}
```

---

## 四、⚠️ 容易写错的地方

### 1. 第一节第 1 问：**不需要**

后端 `get_user_menu_tree()` 已经做完全部过滤（`v0.11.0`）：
自底向上标记有权限的菜单、向上保留祖先目录、空目录自动消失。

```vue
<!-- ❌ 重复实现了后端的过滤逻辑 -->
<a-menu :items="menus.filter((m) => can(m.permCode)).map(...)" />
```

这是 `V-ADR-015`（前端不做数据二次过滤）在菜单上的形态。
再过滤一遍的后果：**两套逻辑必然漂移**——后端改了「空目录」判定，前端不知道。

### 2. 第一节第 2 问：纯函数，不是组件里内联

```vue
<!-- ❌ 没法单测，改一次要跑整个应用 -->
<a-menu :items="menus.map((m) => ({ key: m.routePath, label: m.name }))" />

<!-- ✅ -->
<a-menu :items="menuItems" />
```

```ts
const menuItems = computed(() => toMenuItems(auth.menus))
```

`toMenuItems` 是纯函数 → `vue-v0.13.0` 可以直接单测，输入一棵树，
断言输出结构，**零 mock**。

⚠️ 用 `computed` 而不是直接调用——`vue-v0.11.0` 之后 `menus` 会运行时变化。
直接调用的话菜单**永远不更新**（[04 对比文档第 1 节](../04-React与Vue3做法对比.md#1-响应式模型不可变重渲染--可变代理依赖追踪)）。

### 3. 图标映射要有兜底

```ts
// ❌ undefined 组件会让整个菜单崩溃
const Icon = ICONS[name]

// ✅
const Icon = ICONS[name.toLowerCase()] ?? AppstoreOutlined
```

**一个配错的图标名不能让整个侧边栏崩掉**（同后端 `v0.11.0` 对
`NoReverseMatch` 的处理思路）。

### 4. 📌 图标名的大小写混乱——这次是**第三个**前端在看同一个问题

数据库里的图标名是 `ticket` / `FileText` / `shield` / `UsergroupAdd`，
**大小写都不统一**。

`fe-v0.8.0` 已经记录过原因：这批名字是给 Django 模板版（Lucide 图标集）写的，
而 SPA 用的是 AntD 图标集。

> 📌 **Vue 版是第三个前端，看到的是同一个问题，而且它更明显了。**
>
> `F-ADR-008` 说「后端只下发语义、不下发实现」没有做彻底——
> `icon` 字段名义上是语义，实际上已经是某一个前端的实现细节。
>
> React 版当时的处理是「保留现状 + `toLowerCase()` 归一」，
> 理由是「让你**看见**共用后端真实会遇到的摩擦」。
>
> **Vue 版继续保留这个处理，不修。** 现在有三个前端各自维护一份图标映射表，
> 摩擦从「预言」变成了「可测量的事实」：
> 加一个新菜单要改**三处**前端映射，而漏改的表现是「显示了默认图标」——
> 不报错、不崩溃、没人发现。
>
> 彻底的做法是后端下发**语义名**（`list` / `org` / `audit`），
> 每个前端各自映射。**要不要现在就改？** 见第九节延伸思考 2。

### 5. 第一节第 3 问：**应该高亮**

用户在 `/tickets/42` 时，侧边栏「工单列表」应该是选中态，
否则会觉得自己「不在任何菜单里」。

```ts
// 找出所有「是当前路径前缀」的菜单项，取最长的那个
const matched = flat
  .filter((m) => path === m.routePath || path.startsWith(m.routePath + '/'))
  .sort((a, b) => b.routePath.length - a.routePath.length)[0]
```

⚠️ `startsWith(p + '/')` 的斜杠——不加的话 `/tickets-archive`
会被误判为 `/tickets` 的子路径。

> **同一个坑第五次出现了**（部门树 path 尾斜杠、`ORDER BY path` 排序、
> `fe-v0.8.0` 菜单高亮、`vue-v0.5.0` 的 403/404 分流、这里）。
>
> **字符串前缀匹配必须带分隔符。** 这条可以贴在墙上了。

### 6. 第一节第 4 问：**不该强制展开回去**

```ts
const openKeys = ref<string[]>([])

// ⚠️ 并入，不是覆盖
watch(() => active.value.openKeys, (next) => {
  const added = next.filter((k) => !openKeys.value.includes(k))
  if (added.length) openKeys.value = [...openKeys.value, ...added]
})
```

**覆盖式赋值**（`openKeys.value = next`）会把用户手动展开的其它目录抹掉。

> `fe-v0.8.0` 第一版就写成了覆盖，实现时才改。原话值得再抄一遍：
>
> > 「自动展开」是导航的**辅助**，任何时候都不该压过用户的显式操作。

⚠️ Vue 里 `a-menu` 的 `openKeys` 用 `v-model:open-keys` 双向绑定，
用户操作会直接写回 ref——比 React 的「受控 + onOpenChange」少一步。
但**这也意味着 `watch` 的写入和用户的写入会竞争同一个 ref**，
所以上面必须是「并入」而不是「覆盖」。

### 7. 路由变化的监听：`route.path` 天生响应式

```ts
const route = useRoute()
const active = computed(() => findActiveKeys(auth.menus, route.path))
```

不需要订阅、不需要 `useLocation()`、不需要依赖数组。
`useRoute()` 返回的是响应式对象，`computed` 自动追踪。

🟡 React 版要 `const location = useLocation()` + `useMemo(..., [location.pathname])`。
**同构改写，Vue 少一步。**

### 8. `no_role` 要有说明文案

```vue
<div v-if="!auth.menus.length" class="empty-hint">
  你还没有任何菜单权限，请联系系统管理员。
</div>
```

空白会让用户以为系统坏了。⚠️ 这条文案 `vue-v0.14.0` 的 E2E 会断言，
**文案必须与 React 版逐字相同**。

---

## 五、卡住了看这里

<details>
<summary><b>提示：menuAdapter</b></summary>

```ts
export function toMenuItems(menus: MenuNode[]): ItemType[] {
  return menus.map((node) => {
    const Icon = ICONS[node.icon?.toLowerCase() ?? ''] ?? AppstoreOutlined
    const base = {
      key: node.routePath ?? `cat-${node.id}`,
      icon: () => h(Icon),        // ⚠️ antdv 的 items 里 icon 是**渲染函数**
      label: node.name,
    }
    // 后端已保证空目录不会返回（v0.11.0 自底向上算法），这里不再判断
    return node.children.length
      ? { ...base, children: toMenuItems(node.children) }
      : base
  })
}
```

⚠️ `icon: () => h(Icon)` —— antdv 的 `items` 配置里 icon 要的是渲染函数
而不是 VNode。写成 `icon: h(Icon)` 会导致**所有菜单项共用同一个 VNode 实例**，
表现是图标随机错位。
</details>

---

## 六、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `superadmin` | 全部菜单 |
| 2 | `cs_manager` | 只有「工单管理」 |
| 3 | `cs_staff` | 只有「工单管理」 |
| 4 | ⚠️ `cs_staff` | **看不到「用户管理」**（`vue-v0.3.0` 用例 6 的期望反过来了） |
| 5 | `no_role` | 菜单为空，**有提示文案** |
| 6 | 空目录 | 不渲染（后端已保证） |
| 7 | 在 `/tickets/42` | 「工单列表」高亮，父目录展开 |
| 8 | 手动折叠父目录后导航 | **不被强制展开回去** |
| 9 | 后端把某个 `icon` 改成不存在的名字 | 显示默认图标，**菜单不崩** |
| 10 | 折叠侧边栏 | 只显示图标，hover 出浮层 |
| 11 | 后端 `pytest` / React 版单测 | 全绿 |

---

## 七、和我的实现对比什么

```bash
diff -u frontend/src/layouts/menuAdapter.tsx frontend-vue/src/layouts/menuAdapter.ts
git diff vue-v0.5.0 vue-v0.6.0 -- frontend-vue/
```

> **这个 diff 应该很干净。** 如果混了一堆样式改动，说明 `vue-v0.3.0` 没做扎实。

| 对比点 | 想一想 |
| --- | --- |
| 前端又过滤了一遍权限吗 | 过滤了的话，后端改「空目录」判定时会不同步 |
| 转换在纯函数里还是组件里 | 在组件里的话，`vue-v0.13.0` 怎么单测？ |
| 用了 `computed` 吗 | 没用的话，`vue-v0.11.0` 的菜单不会更新 |
| 高亮匹配加了 `/` 吗 | 造一个 `/tickets-archive` 试试 |
| `openKeys` 是并入还是覆盖 | 跑用例 8 |

---

## 八、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `findActiveKeys` 逻辑 | 🟢 **逐字相同**（纯函数，与框架无关） |
| `toMenuItems` 逻辑 | 🟢 逻辑相同；🔴 `icon` 要传**渲染函数**而不是 VNode |
| 监听路由变化 | 🟡 `useRoute()` 天生响应式 ← `useLocation()` + `useMemo` |
| `openKeys` 受控 | 🟡 `v-model:open-keys` ← 受控 prop + `onOpenChange` |
| 派生值 | 🔴 必须 `computed`（忘了 → 菜单永不更新） |
| 图标映射 | 🟢 同一个问题第三次出现，**同样不修** |
| 空菜单文案 | 🟢 **必须逐字相同**（E2E 要断言） |

**本 tag 的结论**：菜单层的**逻辑**完全与框架无关（纯函数逐字相同），
差异只在「怎么把结果喂给 UI 组件」这一层。

---

## 九、延伸思考

1. `findActiveKeys` 在两个前端里逐字相同。**那它应该被抽成共享包吗？**
   先看 [V-ADR-001](../02-设计文档.md) 再回答——
   本项目的答案和普通项目的答案是相反的，**说清楚为什么**。

2. 图标名的问题现在有三个前端在承担。**要不要现在就改成语义名？**
   改的话：后端加一次迁移、三个前端各改一次映射表。
   不改的话：每加一个菜单要改三处，漏改**不报错**。
   **这个取舍的分界线在哪？**（提示：`ADR-005` 说过「领域纯洁性和管理便利性冲突时，
   选后者」——但那是**两个**前端之前说的。）

3. 至此四层体验完成三层（守卫、菜单、还差按钮）。
   用 `cs_staff` 登录，界面已经很干净了。
   **但它安全吗？** 打开 Vue Devtools 把 `auth.perms` 改成 `['*']`，
   看菜单会怎样——**然后想想 `vue-v0.14.0` 要证明什么。**
