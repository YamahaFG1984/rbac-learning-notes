import { useEffect, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Alert, App, Modal, Radio, Spin, Tree } from 'antd'
import type { DataNode } from 'antd/es/tree'

import { fetchDataScope, saveDataScope, type Role } from '@/api/admin'

interface Props {
  role: Role | null
  onClose: () => void
  onSaved: () => void
}

export function RoleDataScope({ role, onClose, onSaved }: Props) {
  const { message } = App.useApp()
  const [scope, setScope] = useState<number | null>(null)
  const [checkedKeys, setCheckedKeys] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const query = useQuery({
    queryKey: ['role-data-scope', role?.id],
    queryFn: () => fetchDataScope(role!.id),
    enabled: role !== null,
  })

  useEffect(() => {
    if (!query.data) return
    setScope(query.data.dataScope)
    setCheckedKeys(query.data.departments.filter((d) => d.checked).map((d) => d.id))
  }, [query.data])

  const treeData = useMemo<DataNode[]>(() => {
    if (!query.data) return []
    const byParent = new Map<number | null, typeof query.data.departments>()
    for (const d of query.data.departments) {
      const list = byParent.get(d.parent) ?? []
      list.push(d)
      byParent.set(d.parent, list)
    }
    const build = (parent: number | null): DataNode[] =>
      (byParent.get(parent) ?? []).map((d) => ({
        key: d.id,
        title: d.name,
        children: build(d.id),
      }))
    return build(null)
  }, [query.data])

  const isCustom = scope === query.data?.customValue

  const handleSave = async () => {
    if (!role || scope === null) return
    setSaving(true)
    try {
      /*
       * ⚠️ 只提交用户勾了哪几个部门，**不展开子树**。
       *
       *    后端 get_role_custom_dept_ids() 在查询时才展开。
       *    前端提前展开的话，将来新增的子部门永远进不了这个范围——
       *    而管理员勾「客服部」时的意图几乎肯定包含「以后新建的下级」。
       */
      await saveDataScope(role.id, scope, isCustom ? checkedKeys : [])
      message.success('数据范围已更新')
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={role !== null}
      title={`数据范围：${role?.name ?? ''}`}
      width={560}
      onCancel={onClose}
      onOk={handleSave}
      confirmLoading={saving}
      destroyOnHidden
    >
      {query.isLoading || scope === null ? (
        <Spin />
      ) : (
        <>
          <Radio.Group
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            options={query.data!.scopes.map((s) => ({
              value: s.value,
              label: s.label,
            }))}
          />

          {isCustom && (
            <div style={{ marginTop: 16 }}>
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message="勾选的部门**包含其所有下级**"
                description="以后在这些部门下新建的子部门会自动包含进来，不需要回来补勾。"
              />
              <Tree
                checkable
                /*
                 * 这里同样用 checkStrictly：勾「客服部」就只提交客服部，
                 * 展开子树是后端的事。让联动自动勾上三个子部门的话，
                 * 提交的就变成 4 个 id，新增子部门后不会自动包含。
                 */
                checkStrictly
                treeData={treeData}
                defaultExpandAll
                checkedKeys={{ checked: checkedKeys, halfChecked: [] }}
                onCheck={(keys) => {
                  const value = Array.isArray(keys) ? keys : keys.checked
                  setCheckedKeys(value as number[])
                }}
              />
            </div>
          )}
        </>
      )}
    </Modal>
  )
}
