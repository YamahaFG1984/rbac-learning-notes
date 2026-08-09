import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * 表格的分页 / 筛选参数，与 URL 的 query 同步。
 *
 * ⚠️ 为什么不用 `ref`？
 *
 *    分页和筛选确实是「客户端状态」，但它属于**地址**而不是**组件**：
 *      - 刷新页面后筛选条件还在
 *      - 链接可以直接分享给同事
 *    这是企业后台的基本预期，用 `ref` 两条都做不到。
 *
 * ⚠️ 分享链接给同事时，他看到的是**同样的筛选、不同的数据**——
 *    数据权限在后端，URL 里带什么参数都改变不了他能看见的范围。
 *    这一点值得自己验证一次（自测用例）。
 *
 * `replace` 而不是 `push` —— 改筛选条件不该在浏览器历史里堆一大堆记录，
 * 否则用户按返回键要点十几次才能离开这个页面。**这个坑与框架无关。**
 *
 * 🟡 与 React 版 `useTableQuery.ts` 的对照：
 *
 *    React 要 `useSearchParams()` 拿到值 + `useMemo` 还原类型 +
 *    `useCallback` 保持 setParams 引用稳定，约 30 行。
 *
 *    Vue 里 `useRoute().query` **本身就是响应式数据源**，
 *    `computed` 自动追踪，不需要订阅层，也不需要保持函数引用稳定
 *    （函数身份不参与依赖追踪）。约 20 行。
 *
 *    → 这一节 Vue 明显更短，短掉的那部分是**「把外部数据源接进响应式系统」
 *      的样板**——Vue Router 内建了它，React Router 把它留给了 hooks。
 */
export function useTableQuery<T extends Record<string, string | number>>(
  defaults: T,
) {
  const route = useRoute()
  const router = useRouter()

  const params = computed<T>(() => {
    const merged = { ...defaults }
    for (const key of Object.keys(defaults) as Array<keyof T & string>) {
      const raw = route.query[key]
      if (typeof raw !== 'string') continue
      // URL 里全是字符串，按默认值的类型还原回去
      merged[key] = (
        typeof defaults[key] === 'number' ? Number(raw) || defaults[key] : raw
      ) as T[keyof T & string]
    }
    return merged
  })

  function setParams(patch: Partial<T>) {
    const next: Record<string, string> = {}
    for (const [k, v] of Object.entries(route.query)) {
      if (typeof v === 'string') next[k] = v
    }
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === '') delete next[k]
      else next[k] = String(v)
    }
    void router.replace({ query: next })
  }

  return { params, setParams }
}
