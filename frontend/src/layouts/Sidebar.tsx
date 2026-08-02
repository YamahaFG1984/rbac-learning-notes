import { useEffect, useMemo, useState } from 'react'

import { AppstoreOutlined } from '@ant-design/icons'
import { Layout, Menu } from 'antd'
import { useLocation, useNavigate } from 'react-router'

import { useAuthStore } from '@/auth/store'
import { useUiStore } from '@/store/uiStore'

import { findActiveKeys, toAntdMenuItems } from './menuAdapter'

export function Sidebar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const collapsed = useUiStore((s) => s.siderCollapsed)
  const menus = useAuthStore((s) => s.menus)

  const items = useMemo(() => toAntdMenuItems(menus), [menus])
  const active = useMemo(
    () => findActiveKeys(menus, pathname),
    [menus, pathname],
  )

  /**
   * openKeys 受控，但只在**路径变化**时重算。
   *
   * ⚠️ 如果每次渲染都用 active.openKeys 覆盖，用户手动折叠的目录
   *    会立刻被展开回去——看起来像「折叠按钮坏了」。
   *    自动展开是导航的辅助，不该压过用户的显式操作。
   */
  const [openKeys, setOpenKeys] = useState<string[]>(active.openKeys)
  useEffect(() => {
    setOpenKeys((prev) => {
      const next = active.openKeys.filter((k) => !prev.includes(k))
      return next.length > 0 ? [...prev, ...next] : prev
    })
  }, [active.openKeys])

  return (
    <Layout.Sider collapsed={collapsed} theme="dark" width={220}>
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 600,
          letterSpacing: 1,
        }}
      >
        {collapsed ? <AppstoreOutlined /> : 'RBAC 教学系统'}
      </div>

      {menus.length === 0 ? (
        /*
         * ⚠️ no_role 用户菜单为空。渲染一个空的 <Menu /> 会得到一片纯黑，
         *    用户无法区分「我没有权限」和「系统坏了」。
         *    空状态必须有文案——同 fe-v0.7.0 的 HomeRedirect。
         */
        !collapsed && (
          <div
            style={{
              padding: '16px 20px',
              color: 'rgba(255,255,255,0.45)',
              fontSize: 13,
              lineHeight: 1.8,
            }}
          >
            你还没有任何菜单权限，
            <br />
            请联系系统管理员分配角色。
          </div>
        )
      ) : (
        <Menu
          theme="dark"
          mode="inline"
          items={items}
          selectedKeys={active.selectedKeys}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          /*
           * 目录节点的 key 是 catalog-<id>，点它只应展开/折叠，不该导航。
           * AntD 的 onClick 只会在叶子节点触发，但显式挡一道更稳。
           */
          onClick={({ key }) => {
            if (key.startsWith('/')) navigate(key)
          }}
        />
      )}
    </Layout.Sider>
  )
}
