import {
  AppstoreOutlined,
  BarChartOutlined,
  ContainerOutlined,
  FileTextOutlined,
  KeyOutlined,
  ProfileOutlined,
  SafetyCertificateOutlined,
  ApartmentOutlined,
  TeamOutlined,
  UsergroupAddOutlined,
} from '@ant-design/icons'
import type { ComponentType } from 'react'

/**
 * 后端存的图标名 → AntD 图标组件。
 *
 * ⚠️ 这张表本身就是一个信号：**图标名是后端下发的字符串，
 *    而字符串和组件之间没有任何类型约束**。后端把 "FileText" 改成
 *    "Filetext"，TypeScript 一声不吭，运行时才炸。
 *
 * ⚠️ 注意 key 的大小写是乱的（'ticket' 小写、'FileText' 驼峰）——
 *    因为这批图标名是给 Django 模板版（Lucide 图标集）写的，
 *    SPA 用的是 AntD 图标集。**同一份菜单数据要喂两套图标体系**，
 *    这是 F-ADR-008「后端只下发语义、不下发实现」没做彻底的地方：
 *    图标名其实已经是一种实现细节了。
 *
 *    正确的做法是后端下发语义名（"list" / "org" / "audit"），
 *    每个前端各自映射。这里保留现状并做大小写归一，
 *    是为了让你看见「共用后端」真实会遇到的摩擦。
 */
const ICONS: Record<string, ComponentType> = {
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
 *    `const Icon = ICONS[name]; return <Icon />` 在 name 拼错时
 *    等价于 `<undefined />`，React 直接抛错，**整个侧边栏白屏**——
 *    一个配错的图标名不该让用户失去导航能力。
 *
 *    同后端 v0.11.0 对 NoReverseMatch 的处理：降级，不崩。
 */
export function resolveIcon(name: string | null | undefined): ComponentType {
  if (!name) return AppstoreOutlined
  return ICONS[name.toLowerCase()] ?? AppstoreOutlined
}
