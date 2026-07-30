"""模板渲染的公共辅助。"""


def build_tree_rows(queryset, order_field="order_num"):
    """把树形 queryset 摊平成带缩进的行，供模板平铺渲染。

    一次查询取出全部节点，在内存里做先序遍历（不递归查库、不递归模板标签）。

    ⚠️ 不能靠 `ORDER BY path` 得到树序：path 是字符串，
       "/2/6/10/" 排在 "/2/6/7/" 前面。同级排序必须显式按 order_num。
    """
    nodes = list(queryset)
    children = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    for siblings in children.values():
        siblings.sort(key=lambda n: (getattr(n, order_field, 0), n.pk))

    present = {n.pk for n in nodes}
    rows = []

    def walk(parent_id, depth):
        for node in children.get(parent_id, []):
            rows.append(
                {
                    "obj": node,
                    "depth": depth,
                    "indent_px": depth * 24,
                    "is_root": depth == 0,
                }
            )
            walk(node.pk, depth + 1)

    walk(None, 0)

    # queryset 被过滤时可能出现「父节点不在结果集里」的孤儿，按自身 depth 补在末尾
    if len(rows) < len(nodes):
        rendered = {r["obj"].pk for r in rows}
        for node in nodes:
            if node.pk not in rendered and node.parent_id not in present:
                rows.append(
                    {
                        "obj": node,
                        "depth": 0,
                        "indent_px": 0,
                        "is_root": True,
                    }
                )
    return rows
