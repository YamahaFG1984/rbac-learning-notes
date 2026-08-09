import {
  ApartmentOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  ContainerOutlined,
  FileTextOutlined,
  KeyOutlined,
  ProfileOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UsergroupAddOutlined,
} from '@ant-design/icons-vue'
import type { Component } from 'vue'

/**
 * 后端存的图标名 → antdv 图标组件。
 *
 * ⚠️ 这张表本身就是一个信号：**图标名是后端下发的字符串，
 *    而字符串和组件之间没有任何类型约束**。后端把 "FileText" 改成
 *    "Filetext"，TypeScript 一声不吭，运行时才炸。
 *
 * ⚠️ 注意 key 的大小写是乱的（'ticket' 小写、'FileText' 驼峰）——
 *    因为这批图标名是给 Django 模板版（Lucide 图标集）写的，
 *    SPA 用的是 AntD 图标集。
 *
 * 📌 **到 Vue 版为止，同一份菜单数据要喂三套图标体系了。**
 *
 *    `F-ADR-008`「后端只下发语义、不下发实现」没做彻底：
 *    `icon` 字段名义上是语义，实际已经是某一个前端的实现细节。
 *
 *    React 版当时保留现状 + `toLowerCase()` 归一，理由是
 *    「让你**看见**共用后端真实会遇到的摩擦」。
 *
 *    **Vue 版继续保留，不修。** 现在摩擦从「预言」变成了可测量的事实：
 *    加一个新菜单要改**三处**前端映射表，而漏改的表现是
 *    「显示了默认图标」——不报错、不崩溃、没人发现。
 *
 *    ⚠️ 这张表与 React 版 `iconMap.tsx` 的映射内容**逐字相同**，
 *       只有 import 来源和类型不同。**它本该是后端的一张表。**
 */
const ICONS: Record<string, Component> = {
  ticket: ContainerOutlined,
  filetext: FileTextOutlined,
  shield: SafetyCertificateOutlined,
  usergroupadd: UsergroupAddOutlined,
  key: KeyOutlined,
  chart: BarChartOutlined,
  profile: ProfileOutlined,
  building: ApartmentOutlined,
  team: TeamOutlined,
  sitemap: ApartmentOutlined,
}

/**
 * ⚠️ 必须有兜底。
 *
 *    `ICONS[name]` 在 name 拼错时是 `undefined`，
 *    渲染 `undefined` 组件会让**整个侧边栏崩掉**——
 *    一个配错的图标名不该让用户失去导航能力。
 *
 *    同后端 v0.11.0 对 NoReverseMatch 的处理：降级，不崩。
 */
export function resolveIcon(name: string | null | undefined): Component {
  if (!name) return AppstoreOutlined
  return ICONS[name.toLowerCase()] ?? AppstoreOutlined
}
