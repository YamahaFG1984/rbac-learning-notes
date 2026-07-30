"""模板渲染的公共辅助。"""


def build_tree_rows(queryset):
    """把树形 queryset 摊平成带缩进的行，供模板平铺渲染。

    按 path 排序天然就是先序遍历顺序（路径枚举方案的附带好处），
    所以不需要递归模板标签——一次查询，零递归。
    """
    rows = []
    for obj in queryset:
        rows.append(
            {
                "obj": obj,
                "depth": obj.depth,
                "indent_px": obj.depth * 24,
                "is_root": obj.depth == 0,
            }
        )
    return rows
