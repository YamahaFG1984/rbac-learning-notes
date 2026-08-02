import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * 纯客户端状态（F-ADR-005）。
 *
 * 判据：这份数据的真相在哪？在浏览器 → Zustand；在数据库 → TanStack Query。
 * 侧边栏折叠、主题、表格列宽都没有服务端对应物，
 * 放进 Query 是概念错误（它管的是「服务端状态的缓存」）。
 */
interface UiState {
  siderCollapsed: boolean
  toggleSider: () => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      siderCollapsed: false,
      toggleSider: () => set((s) => ({ siderCollapsed: !s.siderCollapsed })),
    }),
    { name: 'rbac-ui' },
  ),
)
