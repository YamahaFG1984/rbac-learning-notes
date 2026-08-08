# vue-v0.10.0 — 组织、角色、权限、审计管理页

| 项 | 值 |
| --- | --- |
| 需求 | VE-6.2 ~ VE-6.6 |
| 关键 V-ADR | — |
| 预计耗时 | 4 ~ 5 小时 |
| 变更规模 | ~500 行（**本阶段最大的一个 tag**） |
| 上一个 tag | `vue-v0.9.0` |
| React 对应 | [`fe-v0.12.0`](../../frontend/tags/12-fe-v0.12.0-组织与权限管理页.md) |

> ⚠️ 本 tag 页面多但**权限概念少**——大部分是 `vue-v0.7.0` / `vue-v0.9.0`
> 已有模式的重复应用。真正需要想清楚的只有**角色的权限树**和**数据范围配置**。

---

## 一、动手之前，先自己想清楚

1. 部门树、权限点树的接口**会分页吗**？如果会，用一棵不完整的树渲染会发生什么？
2. 角色的权限树里，**继承来的权限**该怎么显示？能取消勾选吗？
3. antdv `a-tree` 的父子联动默认是开着的。权限场景下该开还是关？
4. 数据范围选 `CUSTOM` 时要选部门。**保存时提交哪些 ID？**

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `src/api/admin.ts` | 部门/用户/角色/权限/审计请求（**从 React 版复制**） |
| 新建 | `src/pages/system/Departments.vue` | 部门树 + 增删改 |
| 新建 | `src/pages/system/Users.vue` | 用户列表 + 分配角色 |
| 新建 | `src/pages/system/Roles.vue` | 角色列表 |
| 新建 | `src/pages/system/Permissions.vue` | 权限点只读树 |
| 新建 | `src/pages/monitor/AuditLogs.vue` | 审计日志 |
| 新建 | `src/features/roles/RolePermTree.vue` | 🔴 权限树（含继承态） |
| 新建 | `src/features/roles/RoleDataScope.vue` | 🔴 数据范围配置 |

---

## 三、⚠️ 容易写错的地方

### 1. 🔴 第一节第 1 问：**树不能分页**

后端已经修好了（`pagination_class = None`），但你要知道**为什么**。

> 📌 `fe-v0.12.0` 踩过：权限点页面只显示 26 个里的 20 个。
> 第一反应是加 `?page_size=500`——**它被静默忽略了**（DRF 没配
> `page_size_query_param`），看起来像生效了。
>
> 真正的问题是：**一个客户端用不完整的节点集合去建树，会静默丢掉整条分支。**
> 不是「少显示几个」，是「有些分支根本不出现」。
>
> 正确的修法是 `pagination_class = None`：**树不能分页。**

⚠️ 验证一次（自测用例 1）：权限点页面必须显示**全部 26 个**。

### 2. 🔴 第一节第 2、3 问：`checkStrictly`，继承态只读

```vue
<a-tree
  v-model:checked-keys="checkedKeys"
  :tree-data="treeData"
  checkable
  :check-strictly="true"
/>
```

**为什么必须 `checkStrictly`**：

不开的话，antdv 会自动做父子联动——勾选父节点自动勾全部子节点，
取消子节点自动取消父节点。而权限场景下：

- 提交给后端的是「这个角色直接拥有哪些权限点」
- **半选状态的父节点会不会被提交？** 联动模式下这个问题的答案依赖组件内部实现
- 而 `catalog` 类型的节点**没有权限码**（`code=None`），它根本不该被提交

> **权限场景一律 `checkStrictly` —— 必须完全掌控「哪些 key 会被提交」。**
> 这条与框架无关（antd 和 antdv 都有这个属性，行为一致）。

**继承来的权限**（`inherited: true`）：

```ts
// 后端 apps/rbac/perm_tree.py 已经算好了：
//   row.inherited = 来自父角色（不可取消）
//   row.checked   = 直接拥有 或 继承
disabled: row.inherited      // ⚠️ 继承的置灰，不能取消
```

⚠️ **不要在前端自己算继承**。后端 `annotate_role_perm_rows()` 已经算好，
前端再算一遍就是复制了一份角色继承规则（`F-ADR-006`）。

### 3. 第一节第 4 问：只提交 `CUSTOM` 时的部门 ID

```ts
const payload = {
  data_scope: scope.value,
  // ⚠️ 非 CUSTOM 时不提交部门，否则后端会存一堆无意义的关联
  department_ids: scope.value === DataScope.CUSTOM ? selectedDeptIds.value : [],
}
```

⚠️ 数据范围**必须走后端的 `save_role_scope()`**（`apps/rbac/scope_config.py`），
它负责发 `role_scope_changed` 信号 → 写审计日志。

> 📌 `fe-v0.12.0` 挖出的第二个真实问题：
> `AuditAction.ROLE_SCOPE_SET` **定义了却从来没有人发出**——
> 改一个角色的数据范围**完全没有审计痕迹**，而 `FR-9.2` 是 P0。
>
> 不报错、不缺功能，只是那条日志永远不会出现。
> 后端已经修好了，**Vue 版直接受益**。但要验证一次（自测用例 7）。

### 4. 权限树的 `computed` 陷阱

```ts
// ❌ 权限变更后树不更新
const treeData = toTreeData(rows)

// ✅
const treeData = computed(() => toTreeData(rows.value))
```

本 tag 页面多，`computed` 漏写的机会也多。**逐个检查。**

### 5. 表单里**永远不要**出现 `is_superuser`

安全红线第 4 条：

> `is_superuser` 永不出现在任何 Web 表单里。超管只能通过 `createsuperuser` 创建。
> 否则任何有 `system:user:update` 权限的人都能自我提权。

⚠️ 后端序列化器已经排除了它，但**前端也不该显示这个字段**——
显示一个提交上去会被忽略的开关，是在误导使用者。

### 6. 审计日志**不做数据权限过滤**

```
审计员是来审计管理员的。给审计日志加数据范围过滤，
等于让被审计的人决定审计员能看到什么。
```

后端 `AuditLogViewSet` 刻意不加 `.for_user()`——这是**设计**，不是遗漏。
前端不要「顺手」加个部门筛选默认值。

### 7. Modal 的销毁属性：antdv 用 `destroyOnClose`

```vue
<!-- ✅ antdv 4 -->
<a-modal v-model:open="visible" destroy-on-close>
```

⚠️ React 版 antd 6 里 `destroyOnClose` 已废弃，要用 `destroyOnHidden`。
**照抄 React 版会写出一个无效属性**——本阶段第三次遇到同一类问题
（`vue-v0.2.0` 的 `autoInsertSpace`、`vue-v0.3.0` 的 `Spin.tip`）。

> 📌 规律已经很清楚了：**从 antd 6 往 antdv 4 抄，等于从新版本往旧版本抄。**
> React 版注释里写着「XXX 已废弃，用 YYY」的地方，Vue 版大概率要用回那个 XXX。
>
> ⚠️ 不销毁的后果在权限场景下是实的：**上一个角色的权限树勾选状态会残留**，
> 打开另一个角色时看到的是错的。

### 8. 每个页面都要有对应的 `<Can>` + 后端校验

本 tag 新增大量按钮。**每加一个就去确认一次后端有没有对应的 `perm_map` 项**。
`vue-v0.13.0` 的结构性测试会兜底，但不要指望它——
它只能发现「前端用了后端没有的码」，发现不了「后端漏配了校验」。

---

## 四、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | 🔴 权限点页面 | 显示**全部 26 个节点**（不是 20 个）。⚠️ 其中 22 个有权限码，4 个是 `catalog` 容器 |
| 2 | 部门树 | 完整多层，无缺失分支 |
| 3 | 角色权限树 | 继承来的**置灰不可取消**，直接拥有的可勾选 |
| 4 | 勾选一个父节点 | **不自动勾选子节点**（`checkStrictly`） |
| 5 | 保存角色权限 | 提交的 key 里**没有** catalog 节点 |
| 6 | 数据范围选 `DEPT_AND_BELOW` | 部门选择器隐藏，提交 `department_ids: []` |
| 7 | 🔴 改一个角色的数据范围后看审计日志 | **有一条 `ROLE_SCOPE_SET`** |
| 8 | `cs_manager` 访问 `/system/users` | **403 页面** |
| 9 | 打开角色 A 的权限树，关闭，打开角色 B | B 的勾选是**对的**（不是 A 的残留） |
| 10 | 用户表单 | **没有** `is_superuser` 字段 |
| 11 | 审计日志页 | 不因为角色不同而条数不同 |
| 12 | 后端 `pytest` / React 版单测 | 全绿 |

---

## 五、和我的实现对比什么

```bash
diff -u frontend/src/api/admin.ts frontend-vue/src/api/admin.ts   # 期望：几乎无差异
```

| 对比点 | 想一想 |
| --- | --- |
| 权限树开了 `checkStrictly` 吗 | 跑用例 4、5 |
| 继承态是前端算的还是后端给的 | 前端算的话，角色继承规则就有两份了 |
| Modal 销毁属性写对了吗 | 跑用例 9 |
| 有没有漏写 `computed` | 本 tag 页面最多，最容易漏 |

---

## 六、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `api/admin.ts` | 🟢 **逐字相同** |
| 权限树的 `checkStrictly` | 🟢 **决策相同**，属性名也相同 |
| 继承态由后端给 | 🟢 **决策相同** |
| 数据范围走 `save_role_scope` | 🟢 **相同**（后端红利） |
| 审计不做数据权限 | 🟢 **相同的设计** |
| 树不分页 | 🟢 **相同**（后端已修） |
| Modal 销毁属性 | 🔴 `destroy-on-close` ← `destroyOnHidden`（**UI 库版本世代**） |
| 派生值 | 🔴 必须 `computed` |
| 表单绑值 | 🟡 `v-model` ← 受控组件 |

**本 tag 的结论**：管理页面层**没有任何框架级差异**。
所有差异要么是 UI 库版本，要么是 `computed` 这个已知的响应式要求。

---

## 七、延伸思考

1. `fe-v0.12.0` 挖出了两个真实问题（树分页丢分支、数据范围无审计）。
   **Vue 版一个都没挖出来**，因为它们已经被修好了。
   **这说明「接第 N 个前端」的边际价值是递减的吗？**
   如果是，那接第三个前端的价值在哪？（提示：本阶段的主要交付物是什么？）

2. 「树不能分页」这个问题的表现是**静默丢分支**，而不是报错。
   你的系统里还有哪些「传了一个不被识别的参数，长得像生效了」的地方？

3. 至今为止，本阶段已经三次遇到「照抄 React 版会写出无效属性」。
   **有没有一种机械的办法能挡住这类错误？**
   （提示：antdv 的 props 是运行时校验还是编译期的？`vue-tsc` 管得到吗？）
