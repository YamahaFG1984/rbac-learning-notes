# vue-v0.11.0 — 🔴 权限变更感知

| 项 | 值 |
| --- | --- |
| 需求 | VE-5.1 ~ VE-5.5 |
| 关键 V-ADR | [009](../02-设计文档.md)（`computed` 的债在这里还） |
| 预计耗时 | 2.5 ~ 3 小时 |
| 变更规模 | ~150 行 |
| 上一个 tag | `vue-v0.10.0` |
| React 对应 | [`fe-v0.13.0`](../../frontend/tags/13-fe-v0.13.0-权限变更感知.md) |

> 🎯 **先体验问题，再解决它。**
>
> 开两个浏览器窗口：`superadmin` 在后台改 `cs_manager` 的权限，
> `cs_manager` 停在工单列表页。
>
> **Django 模板版**：刷新 → 按钮消失。
> **现在的 SPA**：怎么点都不消失，除非按 F5 重载整个应用。
>
> **这个现象在模板版根本不存在。** 先看见它。

---

## 一、动手之前，先自己想清楚

1. 后端已经有全局版本号（`v0.16.0` 的 `rbac:version`）和中间件
   （`X-RBAC-Version` 响应头）。**前端要做什么？**
2. 版本号变了就提示「你的权限已更新」，对吗？**想想版本号是全局的。**
3. 用户完全不发请求（停在静态页面）时，怎么感知？
4. 🔴 `await refetchProfile()` 之后，store 里是新值还是旧值？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/api/versionWatcher.ts` | 比对版本号 + 重拉 + 比对新旧 perms |
| 修改 | `src/api/client.ts` | 响应拦截器挂上（**成功和失败分支都要**） |
| 修改 | `src/App.vue` | 注入 `refetchProfile` / `notify` |
| 修改 | `src/pages/Login.vue` | 登出时 `resetVersionWatcher()` |
| 修改 | 🔴 所有漏写 `computed` 的地方 | 本 tag 会把它们全部暴露出来 |

---

## 三、⚠️ 容易写错的地方

### 1. 第一节第 1 问：前端只做「比对 + 重拉」

```ts
export async function watchRbacVersion(response: AxiosResponse) {
  const version = response.headers['x-rbac-version'] as string | undefined
  if (!version) return

  /*
   * ⚠️ 两个条件缺一不可：
   *
   *   lastSeen !== null  —— **第一次**收到版本号时不能 invalidate。
   *                         那时 profile 刚拉完，再拉一次是浪费；
   *                         而且 profile 请求本身也带回版本号，
   *                         无条件 invalidate 会形成**无限循环**。
   *
   *   version !== lastSeen —— 没变就什么都不做。每次响应都 invalidate
   *                           等价于「每个请求都重拉一次 profile」。
   */
  const changed = lastSeen !== null && version !== lastSeen
  lastSeen = version
  if (!changed || !refetchProfile) return
  ...
}
```

**这段与 React 版逐字相同。** 它是纯逻辑，与框架无关。

### 2. 🔴 第一节第 2 问：**不对**，会大面积误报

版本号是**全局**的（后端 `ADR-010` 的已知取舍）：
**任何人改权限，所有在线用户都会走到这里。**

```ts
// ❌ 所有在线用户都收到「你的权限已更新」，而 99% 的人权限根本没动
if (changed) notify('你的权限已更新')

// ✅ 重拉之后比对新旧 perms，真的变了才提示
const before = auth.perms.slice()          // ⚠️ slice()！见陷阱 4
const fresh = await refetchProfile()
if (!fresh) return
if (!sameSet(before, fresh.perms)) notify('你的权限已更新')
```

### 3. 错误响应也要比对版本号

```ts
client.interceptors.response.use(
  (response) => { void watchRbacVersion(response); return response },
  (error) => {
    // ⚠️ 错误响应也带版本号 —— 而且这恰恰是最需要它的时候：
    //    权限刚被撤销时，用户碰到的第一个响应往往就是 403。
    if (error.response) void watchRbacVersion(error.response)
    ...
  },
)
```

漏掉的表现：撤权后用户点按钮 → 403 → 提示「无权限」→ 但按钮**还在**，
再点还是 403。用户会一直点。

### 4. 🔴🔴 第一节第 4 问 —— **本 tag 的核心，也是本阶段一个待验证项**

React 版在这里踩过一个真实的坑，`versionWatcher.ts` 的注释完整记着：

> `refetchProfile` 必须**返回拉到的新 profile**，不能只返回 void 让调用方回头去读 store。
>
> 原因是时序：store 的写入走的是 `useProfileQuery` 里的 `useEffect`，
> 而 `useEffect` 要等 React 重新渲染才跑。
> **`await refetchQueries()` 解决的那一刻，store 里还是旧值。**
>
> 我第一版就是读 store 比对的，结果是：按钮确实消失了（React 后来渲染了），
> 但**提示永远不弹**（比对时新旧一样）。
> 这个 bug 只在 E2E 里能发现——**单测里 mock 的 refetch 是同步改 store 的**。

**Vue 版用 `watch` 做同一件事。这个窗口还在吗？**

| | React `useEffect` | Vue `watch`（默认 `flush: 'pre'`） |
| --- | --- | --- |
| 触发时机 | 渲染**提交后** | 组件更新**前**（同一 tick 内） |
| `await refetch()` 之后 | ❌ 尚未执行 | ⚠️ **可能已执行，也可能没有** |

🎯 **本 tag 要求你实测一次**，并把结论回填到
[04 对比文档第 11 节](../04-React与Vue3做法对比.md#11-把-query-的结果写进-store一个跨框架的时序陷阱)
和「附：还没验证的三件事」第 1 条。

怎么测：

```ts
const before = auth.perms.slice()
await refetchProfile()
console.log('store 里是新值吗？', auth.perms, before)
```

**无论实测结果如何，都保留 React 版的解法**：

```ts
// ✅ 直接用返回值，不绕道读 store
const fresh = await refetchProfile()
if (!sameSet(before, fresh.perms)) notify('你的权限已更新')
```

理由：那条规则（**「异步操作完成」≠「派生状态已更新」**）是对的，
**即使某个框架的某个版本恰好让你侥幸过关。**

### 5. ⚠️ `before` 必须 `slice()`——Vue 特有的陷阱

```ts
// ❌ Pinia 的 perms 是响应式数组，setProfile 之后**这个引用指向的内容也变了**
const before = auth.perms
await refetchProfile()
sameSet(before, fresh.perms)      // 永远相等！

// ✅
const before = auth.perms.slice()
```

**React 版不需要这一步**——Zustand 的 `set({ perms: newArray })` 是**替换引用**，
旧引用指向的旧数组不变。

> 🔴 **这是「可变代理 vs 不可变更新」差异的一个非常具体的后果。**
> 而且它的表现和陷阱 4 一模一样：**提示永远不弹**。
> 两个不同的原因，同一个症状。

### 6. 🔴 本 tag 会把之前所有漏写的 `computed` 全部暴露出来

在此之前 `perms` 拉回来一次就不变了，所以：

- 忘了 `computed` 的派生值 → 看不出来
- 忘了 `storeToRefs` 的解构 → 看不出来
- `columns` 写成普通数组 → 看不出来

**现在它们会一起炸。** 症状是「权限撤销了，但某些按钮/菜单/列不消失」。

⚠️ **不要一个个救火**，先把 `vue-v0.4.0` ~ `vue-v0.10.0` 的派生值扫一遍。
自测用例 4~7 是分层验证。

> 📌 这就是 [04 对比文档](../04-React与Vue3做法对比.md)那句总纲的现场：
> **Vue 的失误方向是「该更新的不更新」，而它会一直潜伏到状态真的运行时变化的那一刻。**

### 7. 第一节第 3 问：403 兜底（`VE-5.4`）

用户完全不发请求时感知不到。→ 收到 403 时**强制重拉 profile**
（可能是权限刚被撤销）。这在 `vue-v0.12.0` 的 `errorHandlers` 里实现。

### 8. 登出必须 `resetVersionWatcher()`

```ts
// ⚠️ 不重置的话，下一个用户登录时 lastSeen 还是上一个会话的值，
//    第一个响应就会被判定为「版本变了」，白白多拉一次 profile。
export function resetVersionWatcher() { lastSeen = null }
```

现在登出要清**五样**了：

```ts
await logout()
auth.reset()
queryClient.clear()
resetVersionWatcher()
clearDynamicRoutes()      // 🔴 Vue 独有的第五样（vue-v0.5.0）
```

---

## 四、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 🎯 两窗口：管理员撤销 `cs_manager` 的删除权限，`cs_manager` 点任意按钮 | 删除按钮**消失**，出现「你的权限已更新」 |
| 2 | 全程 | **不需要刷新页面，不需要重新登录** |
| 3 | 管理员改的是**别人**的权限 | `cs_manager` **不弹提示**（不误报） |
| 4 | 撤权后：菜单 | 对应菜单项消失 |
| 5 | 撤权后：表格「操作」列 | 消失（`columns` 是 `computed` 吗？） |
| 6 | 撤权后：页面里的 `<Can>` 按钮 | 全部消失 |
| 7 | 🔴 **恢复**权限 | 按钮/菜单/列**全部回来** |
| 8 | 撤权后直接点那个按钮 | 403 → 提示 → 按钮消失（错误分支也比对了版本） |
| 9 | 登出后换账号 | 不多拉一次 profile（`lastSeen` 已重置） |
| 10 | 🎯 实测 `await refetchProfile()` 后 store 是新值吗 | **记下结果，回填 04 文档** |
| 11 | 后端 `pytest` / React 版单测 | 全绿 |

⚠️ **用例 7 是指令方案的判决**（`vue-v0.7.0` 缺陷 2）。
如果你当时用了 `v-perm`，这一条**做不到**。

---

## 五、和我的实现对比什么

```bash
diff -u frontend/src/api/versionWatcher.ts frontend-vue/src/api/versionWatcher.ts
```

**期望：核心逻辑逐字相同，只有 `before = auth.perms.slice()` 这一处不同。**

| 对比点 | 想一想 |
| --- | --- |
| `lastSeen !== null` 这个条件在吗 | 去掉试试，看会不会无限循环 |
| 重拉之后比对新旧 perms 了吗 | 没比对的话跑用例 3 |
| `before` 有没有 `slice()` | 没有的话提示永远不弹 |
| 错误分支也 watch 了吗 | 跑用例 8 |
| 登出清了五样吗 | 少一样，哪个用例会红？ |

---

## 六、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `watchRbacVersion` 的核心逻辑 | 🟢 **逐字相同**（纯逻辑） |
| 两个条件（`lastSeen !== null` + `changed`） | 🟢 **逐字相同** |
| 重拉后比对新旧 perms | 🟢 **决策相同**（实测：改别人的权限确实不弹提示） |
| 注入模式 | 🟢 **形状相同**（`configureVersionWatcher`） |
| **`refetchProfile` 的实现** | 🔴🔴 **不能照抄** `refetchQueries(['profile'])`——那是空操作（见下） |
| React 的 `useEffect` 时序坑 | 🟢 **在 Vue 版不存在**，但原因不是 `watch` 更快（见下） |
| `before` 快照 | ⚠️📌 **我断言错了**：`slice()` 实测不是必需的（见下） |
| 界面自动更新 | 🟡 Vue 靠 `computed` 自动传播 |
| 登出清理项 | 🟢 **四样，与 React 相同**（`vue-v0.5.0` 把路由清理变成派生效果之后） |

### 🔴📌 实测三个发现

**1. `refetchProfile` 照抄 React 会完全不工作，且不报错**

```ts
await queryClient.refetchQueries({ queryKey: ['profile'] })
return queryClient.getQueryData(['profile'])     // ❌ 永远 undefined
```

`vue-v0.5.0` 把引导挪进守卫后，profile 走的是命令式的 `fetchProfileIntoStore()`，
**从来没进过 vue-query 的缓存**。实测：版本号确实变了（`1` → `6`）、
`changed` 也是 `true`，但函数在 `if (!fresh) return` 悄悄退出。

正确写法：`refetchProfile: () => fetchProfileIntoStore()`。

📌 这是 **V-ADR-005 的第 5 个连锁后果**。一个「守卫放哪」的决定，
一路影响到了「权限变更感知怎么实现」。

**2. React 的 `useEffect` 时序坑在 Vue 版不存在——但不是因为 `watch`**

实测探针：`await refetchProfile()` 那一刻 `storeRightAfterAwait` 已经是新值。

原因是 Vue 版**根本没走 `watch`**：`fetchProfileIntoStore()` 在同一个函数里
先 `await fetchProfile()` 再 `auth.setProfile(profile)`，同步完成。

> React 那个坑存在，是因为「拉取」和「写 store」被 Query + `useEffect` 拆成两步。
> **Vue 把它们合成一步，坑就消失了——而合并的理由完全不相干（守卫用不了 hook）。**

⚠️ 不能读成「Vue 的响应式更及时」。`vue-v0.4.0` 时用的就是
`useProfileQuery` + `watch`，那个窗口大概率同样存在。

**3. ⚠️ `before` 的 `slice()` —— 我断言错了**

初稿写「Vue 必须 slice，否则 Pinia 的响应式数组被原地改掉，提示永远不弹」。
**实测：去掉 slice 之后 `before` 仍是旧值，提示照常弹。**

因为 `setProfile` 写的是 `perms.value = profile.perms`（替换引用），
不是 `perms.value.splice(...)`（原地修改）。

> **「Pinia 的 state 是可变的」不等于「你的代码在原地改它」。**
> 我把「框架允许什么」当成了「代码实际做什么」。

`slice()` 保留，理由改成纯防御。

---

## 七、延伸思考

1. 陷阱 4 和陷阱 5 **症状完全一样**（提示永远不弹），**原因完全不同**
   （一个是 `useEffect` 时序，一个是响应式数组引用）。
   **怎么区分？** 有没有一种写法能同时免疫这两个问题？
   （提示：看看最终采用的解法。）

2. React 版说「这个 bug 只在 E2E 里能发现——单测里 mock 的 refetch 是同步改 store 的」。
   **这条在 Vue 版也成立吗？** 那么：
   **一个把异步简化成同步的 mock，还能证明什么？**

3. `VE-5.3` 承诺「生效延迟 ≤ 一次 API 请求」，与后端 `FR-4.5` 对齐。
   **换了前端框架，这个承诺变了吗？** 为什么？
   这说明「延迟」这个指标是由哪一层决定的？

4. 现在回头看 `vue-v0.7.0` 你写的那句「这份干净的安全价值是多少」。
   **权限变更感知让前端更安全了吗？** 还是只是更好用了？
