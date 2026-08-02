"""角色权限树的标记计算。

⚠️ 单独成模块，是为了让**两个前端共用同一份规则**。

   模板版（v0.12.0）和 SPA 各算一遍的话，迟早不一致——
   而这条规则一旦算错，后果是「保存时把直接授权静默删掉」，
   没有任何报错，只有用户过几天发现自己的权限没了。

⚠️ 刻意**不放进** services.py。

   services.py 是权限内核，ADR-013 的约束是它不认识任何表现层；
   本模块算的是「一棵给人勾选的树长什么样」，那是表现层的关注点，
   只是恰好被两个表现层共用。

   验收条件仍然是：git diff main HEAD -- apps/rbac/services.py 为空。
"""

from apps.rbac.services import get_role_effective_codes


def annotate_role_perm_rows(role, rows):
    """给 build_tree_rows 的结果补上 checked / inherited 两个标记。

    - `checked`   —— 界面上该不该显示成勾选（直接授予 **或** 继承而来）
    - `inherited` —— 该不该禁用（**纯继承、且不是直接授予**）

    🔴 `inherited` 的定义里那个 `and not is_direct` 是本函数存在的全部理由。

       disabled 的 checkbox **不会随表单提交**。如果一个权限既是直接授予、
       又是从父角色继承来的，把它一律禁用，保存时它就不在提交值里——
       于是**直接授权被静默删掉**。

       用户看到的是「我明明勾着，保存完就没了」，而且没有任何报错。

       AntD 的 Tree 有完全一样的行为：disabled 节点不进 checkedKeys。
       所以前端**绝不能自己算 inherited**——它一旦写成
       「在父角色的权限里 = inherited」，就精确地踩回这个坑
       （F-ADR-006：组件禁止自行推断权限）。

    返回传入的 rows（原地修改），方便链式使用。
    """
    from apps.rbac.services import get_role_permission_ids

    direct_ids = get_role_permission_ids(role)

    inherited_codes = set()
    if role.inherits_from_id:
        inherited_codes = set(get_role_effective_codes(role.inherits_from))

    for row in rows:
        obj = row["obj"]
        is_direct = obj.pk in direct_ids
        # catalog 类型没有权限码（code=None），它只是分组容器，不参与继承判断
        row["inherited"] = (
            bool(obj.code) and obj.code in inherited_codes and not is_direct
        )
        row["checked"] = is_direct or row["inherited"]

    return rows


def has_inherited(role) -> bool:
    """这个角色有没有父角色——决定界面上要不要显示图例。"""
    return bool(role.inherits_from_id)
