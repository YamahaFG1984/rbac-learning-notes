<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { Alert, Table, Tag } from 'ant-design-vue'
import { computed } from 'vue'

import { fetchPermissions, type Permission } from '@/api/admin'
import PageContainer from '@/layouts/PageContainer.vue'

interface Row extends Permission {
  children?: Row[]
}

const TYPE_TAG: Record<string, { color: string; text: string }> = {
  catalog: { color: 'default', text: '目录' },
  menu: { color: 'blue', text: '菜单' },
  button: { color: 'green', text: '按钮' },
}

const query = useQuery({
  queryKey: computed(() => ['permissions']),
  queryFn: fetchPermissions,
})

const tree = computed<Row[]>(() => {
  const rows = query.data.value ?? []
  const byParent = new Map<number | null, Permission[]>()
  for (const p of rows) {
    const list = byParent.get(p.parent) ?? []
    list.push(p)
    byParent.set(p.parent, list)
  }
  const build = (parent: number | null): Row[] =>
    (byParent.get(parent) ?? []).map((p) => {
      const children = build(p.id)
      return children.length > 0 ? { ...p, children } : { ...p }
    })
  return build(null)
})

/**
 * 🔴📌 `defaultExpandAllRows` 在**数据异步到达**时不生效（vue-v0.10.0 实测）。
 *
 *    它只在首次渲染时计算一次「默认展开哪些行」，而那时 `dataSource` 还是空数组
 *    （数据来自 useQuery）。数据回来之后默认值不会重算。
 *
 *    表现：树形表格只显示**顶层节点**——权限点 26 个只显示 4 个、
 *    部门 6 个只显示 1 个。**不报错，看起来就像「设计成折叠的」。**
 *
 *    ⚠️ **React 版有一模一样的 bug**（实测：同样是 4 行和 1 行）。
 *       这不是 Vue/React 差异，是 antd/antdv 共有的行为，
 *       而 fe-v0.12.0 的 92 个 E2E 没有断言过行数，所以一直没被发现。
 *       本项目只修 Vue 版（frontend/ 要保持 fe-v1.0.0 原样以供对比），
 *       该发现记在 04 对比文档与本 tag 规格书里。
 *
 *    修法：自己算出全部有子节点的 key，用受控的 expandedRowKeys。
 */
const expandedRowKeys = computed(() => {
  const keys: number[] = []
  const walk = (rows: Row[]) => {
    for (const r of rows) {
      if (r.children?.length) {
        keys.push(r.id)
        walk(r.children)
      }
    }
  }
  walk(tree.value)
  return keys
})

const columns = [
  { title: '名称', dataIndex: 'name' },
  { title: '权限码', dataIndex: 'code', key: 'code', width: 260 },
  { title: '类型', dataIndex: 'perm_type', key: 'perm_type', width: 90 },
  { title: '状态', key: 'status', width: 110 },
]
</script>

<template>
  <PageContainer title="权限点">
    <!--
      ⚠️ 这个页面**只读**，没有任何编辑按钮。

         权限点由 apps/<app>/permissions.py 声明，经 sync_permissions 入库（ADR-004）。
         开一个「新增权限点」的界面，就等于允许运行时凭空造出一个
         代码里没有人检查的权限码——它永远不会生效，却会出现在角色配置里，
         让管理员以为自己授予了什么。

         **权限点的真相在代码里，不在数据库里。**
    -->
    <Alert
      type="info"
      show-icon
      style="margin-bottom: 16px"
      message="权限点由代码声明，此页只读"
      description="新增或修改权限点请改 apps/<app>/permissions.py，再运行 python manage.py sync_permissions。数据库不是权限点的真相来源。"
    />

    <Table
      row-key="id"
      :loading="query.isFetching.value"
      :data-source="tree"
      :columns="columns"
      :pagination="false"
      :expanded-row-keys="expandedRowKeys"
    >
      <template #bodyCell="{ column, record }">
        <!-- catalog 没有权限码，它只是分组容器 -->
        <template v-if="column.key === 'code'">
          <code v-if="(record as Row).code">{{ (record as Row).code }}</code>
          <span v-else style="color: #bfbfbf">—</span>
        </template>

        <template v-else-if="column.key === 'perm_type'">
          <Tag :color="TYPE_TAG[(record as Row).perm_type]?.color">
            {{ TYPE_TAG[(record as Row).perm_type]?.text ?? (record as Row).perm_type }}
          </Tag>
        </template>

        <template v-else-if="column.key === 'status'">
          <!-- 废弃而不是删除：删掉的话，历史授权记录会变成孤儿 -->
          <Tag v-if="(record as Row).is_deprecated" color="orange">已废弃</Tag>
          <Tag v-else-if="(record as Row).is_active" color="green">启用</Tag>
          <Tag v-else>停用</Tag>
        </template>
      </template>
    </Table>
  </PageContainer>
</template>
