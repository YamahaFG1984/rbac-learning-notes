import { useCallback, useMemo } from 'react'

import { useSearchParams } from 'react-router'

/**
 * 表格的分页 / 筛选参数，与 URL 的 search params 同步。
 *
 * ⚠️ 为什么不用 useState？
 *
 *    分页和筛选确实是「客户端状态」，但它属于**地址**而不是**组件**：
 *      - 刷新页面后筛选条件还在
 *      - 链接可以直接分享给同事
 *    这是企业后台的基本预期，用 useState 两条都做不到。
 *
 * ⚠️ 分享链接给同事时，他看到的是**同样的筛选、不同的数据**——
 *    数据权限在后端，URL 里带什么参数都改变不了他能看见的范围。
 *    这一点值得自己验证一次（fe-v0.10.0 自测用例 7）。
 *
 * replace: true —— 改筛选条件不该在浏览器历史里堆一大堆记录，
 * 否则用户按返回键要点十几次才能离开这个页面。
 */
export function useTableQuery<T extends Record<string, string | number>>(
  defaults: T,
) {
  const [searchParams, setSearchParams] = useSearchParams()

  const params = useMemo(() => {
    const merged = { ...defaults }
    for (const key of Object.keys(defaults) as Array<keyof T & string>) {
      const raw = searchParams.get(key)
      if (raw === null) continue
      // URL 里全是字符串，按默认值的类型还原回去
      merged[key] = (
        typeof defaults[key] === 'number' ? Number(raw) || defaults[key] : raw
      ) as T[keyof T & string]
    }
    return merged
    // defaults 通常是模块级常量，引用稳定；不稳定的话这里会每次重算
  }, [searchParams, defaults])

  const setParams = useCallback(
    (patch: Partial<T>) => {
      const next = new URLSearchParams(searchParams)
      for (const [k, v] of Object.entries(patch)) {
        if (v === undefined || v === '') next.delete(k)
        else next.set(k, String(v))
      }
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  return [params, setParams] as const
}
