import { useEffect, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Alert, App, Modal, Spin, Tag, Tree } from 'antd'
import type { DataNode } from 'antd/es/tree'

import {
  fetchRolePermissions,
  saveRolePermissions,
  type PermNode,
  type Role,
} from '@/api/admin'

interface Props {
  role: Role | null
  onClose: () => void
  onSaved: () => void
}

/**
 * 把扁平的权限节点组装成 AntD Tree 的数据。
 *
 * ⚠️ 纯继承的项设 `disabled` + 灰色标签。
 *    「继承来的权限不能在子角色里取消」——那需要「负权限」，本项目不做。
 */
function toTreeData(nodes: PermNode[]): DataNode[] {
  const byParent = new Map<number | null, PermNode[]>()
  for (const n of nodes) {
    const list = byParent.get(n.parent) ?? []
    list.push(n)
    byParent.set(n.parent, list)
  }

  const build = (parent: number | null): DataNode[] =>
    (byParent.get(parent) ?? []).map((n) => ({
      key: n.id,
      disabled: n.inherited,
      title: (
        <span>
          {n.name}
          {n.code && (
            <span style={{ color: '#bfbfbf', marginLeft: 8, fontSize: 12 }}>
              {n.code}
            </span>
          )}
          {n.inherited && (
            <Tag color="default" style={{ marginLeft: 8 }}>
              继承
            </Tag>
          )}
        </span>
      ),
      children: build(n.id),
    }))

  return build(null)
}

export function RolePermTree({ role, onClose, onSaved }: Props) {
  const { message } = App.useApp()
  const [checkedKeys, setCheckedKeys] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const query = useQuery({
    queryKey: ['role-permissions', role?.id],
    queryFn: () => fetchRolePermissions(role!.id),
    enabled: role !== null,
  })

  useEffect(() => {
    if (query.data) setCheckedKeys(query.data.nodes.filter((n) => n.checked).map((n) => n.id))
  }, [query.data])

  const treeData = useMemo(
    () => (query.data ? toTreeData(query.data.nodes) : []),
    [query.data],
  )

  const handleSave = async () => {
    if (!role || !query.data) return
    setSaving(true)
    try {
      /*
       * 🔴 只提交「勾选的」且「不是纯继承的」。
       *
       *    继承来的权限本来就不该出现在提交值里——它属于父角色。
       *    而 disabled 的节点根本进不了 checkedKeys，这里的过滤
       *    是为了防止 checkStrictly 的联动把它们意外带上。
       */
      const inherited = new Set(
        query.data.nodes.filter((n) => n.inherited).map((n) => n.id),
      )
      const payload = checkedKeys.filter((id) => !inherited.has(id))

      const res = await saveRolePermissions(role.id, payload)
      if (res.rejected > 0) {
        // ⚠️ 不能静默丢弃 —— 那会让管理员以为保存成功了（ADR-011）
        message.warning(
          `已保存 ${res.saved} 项；忽略了 ${res.rejected} 项你自己不具备的权限——不能授出自己没有的权限`,
        )
      } else {
        message.success(`已保存 ${res.saved} 项权限`)
      }
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={role !== null}
      title={`配置权限：${role?.name ?? ''}`}
      width={640}
      onCancel={onClose}
      onOk={handleSave}
      confirmLoading={saving}
      destroyOnHidden
    >
      {query.isLoading ? (
        <Spin />
      ) : (
        <>
          {query.data?.hasInherited && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`本角色继承自「${query.data.inheritsFromName}」`}
              description="带「继承」标签的权限来自父角色，不可在这里取消。要取消需修改父角色，或解除继承关系。"
            />
          )}
          <Tree
            checkable
            /*
             * 🔴 checkStrictly：父子节点的勾选**互不联动**。
             *
             *    默认的联动会在勾父节点时把子节点一起带上，
             *    而「哪些 key 会被提交」在权限场景必须是完全可控的——
             *    多带一个 catalog 下的按钮权限，就是多授出一个操作。
             *
             *    代价是用户要逐个勾。这在权限配置页是可以接受的交换：
             *    这个页面一年用不了几次，但每次都事关重大。
             *    （同模板版 v0.5.0 选择手写联动而不用现成组件。）
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
        </>
      )}
    </Modal>
  )
}
