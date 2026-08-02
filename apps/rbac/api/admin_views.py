"""角色权限配置、数据范围、用户角色的 API。

⚠️ 这一层**只做翻译**：把 HTTP 请求翻成对 services.py 的调用，再把结果翻回 JSON。

   所有判断（谁能授出什么、继承怎么展开、部门子树怎么算）都在
   services.py 和 perm_tree.py 里，和模板版调的是同一批函数——
   不是「API 版本」，是同一个（ADR-013）。

   一旦这里出现 `if` 判断权限，就说明规则被抄了第二遍。
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Department, User
from apps.common.views import build_tree_rows
from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role
from apps.rbac.perm_tree import annotate_role_perm_rows, has_inherited
from apps.rbac.permissions import RolePerm
from apps.rbac.scope_config import save_role_scope
from apps.rbac.services import (
    can_grant_role,
    filter_grantable_permission_ids,
    get_role_department_ids,
    get_role_perm_sources,
    get_role_permission_ids,
    get_user_role_ids,
    save_role_permissions,
    save_user_roles,
    user_has_perm,
)
from apps.accounts.permissions import UserPerm


def _require(user, code):
    """函数视图没有 perm_map，只能显式检查。

    ⚠️ 用的是同一个 user_has_perm()，不是另写一套判断。
       rbac.W001/W002 检查的是视图和 ViewSet，这几个函数视图
       落在检查范围之外——所以这里的疏漏没有告警兜底，
       写的时候要格外小心（这本身就是「多一种视图形态 = 多一处要盯」的代价）。
    """
    if not user_has_perm(user, code):
        raise PermissionDenied("你没有该操作的权限")


# --------------------------------------------------------------------------- #
# 角色 → 权限
# --------------------------------------------------------------------------- #


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def role_permissions(request, pk):
    """GET 取权限树（含 checked / inherited 标记），PUT 保存。"""
    role = Role.objects.filter(pk=pk).first()
    if role is None:
        return Response({"detail": "角色不存在"}, status=404)

    if request.method == "PUT":
        _require(request.user, RolePerm.ASSIGN_PERM)

        # 权限不可放大：不能授出自己不具备的权限（ADR-011）。
        # ⚠️ 这一步**必须**在服务端做——前端的树只是界面，
        #    攻击者直接 PUT 一个 id 列表进来是几秒钟的事。
        kept, rejected = filter_grantable_permission_ids(
            request.user,
            request.data.get("permissions", []),
            existing_ids=get_role_permission_ids(role),
        )
        saved = save_role_permissions(role, kept, actor=request.user)
        return Response(
            {
                "saved": len(saved),
                # 告诉前端有多少项被忽略了，而不是静默丢弃——
                # 静默丢弃会让管理员以为保存成功了
                "rejected": len(rejected),
            }
        )

    _require(request.user, RolePerm.VIEW)

    perms = Permission.objects.filter(is_active=True, is_deprecated=False)
    rows = annotate_role_perm_rows(role, build_tree_rows(perms))

    return Response(
        {
            "hasInherited": has_inherited(role),
            "inheritsFromName": (
                role.inherits_from.name if role.inherits_from_id else None
            ),
            "nodes": [
                {
                    "id": row["obj"].pk,
                    "parent": row["obj"].parent_id,
                    "name": row["obj"].name,
                    "code": row["obj"].code,
                    "permType": row["obj"].perm_type,
                    "depth": row["depth"],
                    # 🔴 checked / inherited 由后端给，前端**绝不能自己算**。
                    #    前端一旦写成「在父角色权限里 = inherited」，
                    #    就会把「既直接授予又继承」的项也禁用掉，
                    #    保存时那条直接授权被静默删除（F-ADR-006）。
                    "checked": row["checked"],
                    "inherited": row["inherited"],
                }
                for row in rows
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def role_effective_permissions(request, pk):
    """展开继承后的完整权限，并标注每一项来自哪个角色。

    这个接口看起来是锦上添花，实际是**运维刚需**：
    有人问「为什么张三能删工单」，你必须能在 10 秒内回答。
    """
    _require(request.user, RolePerm.VIEW)

    role = Role.objects.filter(pk=pk).first()
    if role is None:
        return Response({"detail": "角色不存在"}, status=404)

    sources = get_role_perm_sources(role)
    names = dict(
        Permission.objects.filter(code__in=sources.keys(), is_active=True).values_list(
            "code", "name"
        )
    )

    chain, current, depth = [], role, 0
    while current is not None and depth <= 6:
        chain.append({"id": current.pk, "name": current.name})
        current = current.inherits_from
        depth += 1

    return Response(
        {
            "chain": chain,
            "rows": sorted(
                (
                    {
                        "code": code,
                        "name": names.get(code, code),
                        "source": src.name,
                        "isDirect": src.pk == role.pk,
                    }
                    for code, src in sources.items()
                ),
                key=lambda r: r["code"],
            ),
        }
    )


# --------------------------------------------------------------------------- #
# 角色 → 数据范围
# --------------------------------------------------------------------------- #


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def role_data_scope(request, pk):
    role = Role.objects.filter(pk=pk).first()
    if role is None:
        return Response({"detail": "角色不存在"}, status=404)

    if request.method == "PUT":
        _require(request.user, RolePerm.ASSIGN_PERM)
        # 与模板版共用同一个函数 —— 包括它发出的审计信号
        save_role_scope(
            role,
            request.data.get("dataScope", role.data_scope),
            request.data.get("departments", []),
            actor=request.user,
        )
        return Response({"detail": "已更新"})

    _require(request.user, RolePerm.VIEW)

    checked = get_role_department_ids(role)
    rows = build_tree_rows(Department.objects.all())
    return Response(
        {
            "dataScope": role.data_scope,
            "customValue": DataScope.CUSTOM,
            "scopes": [{"value": v, "label": label} for v, label in DataScope.choices],
            "departments": [
                {
                    "id": row["obj"].pk,
                    "parent": row["obj"].parent_id,
                    "name": row["obj"].name,
                    "depth": row["depth"],
                    "checked": row["obj"].pk in checked,
                }
                for row in rows
            ],
        }
    )


# --------------------------------------------------------------------------- #
# 用户 → 角色
# --------------------------------------------------------------------------- #


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def user_roles(request, pk):
    target = User.objects.filter(pk=pk).first()
    if target is None:
        return Response({"detail": "用户不存在"}, status=404)

    if request.method == "PUT":
        _require(request.user, UserPerm.ASSIGN_ROLE)

        granter = request.user
        allowed, refused = [], []
        # 权限不可放大：不能把自己不具备的角色授予他人（ADR-011）
        for role in Role.objects.filter(id__in=request.data.get("roles", [])):
            (allowed if can_grant_role(granter, role) else refused).append(role.pk)

        saved = save_user_roles(target, allowed, granted_by=granter)
        return Response({"saved": len(saved), "rejected": len(refused)})

    _require(request.user, UserPerm.VIEW)

    checked = get_user_role_ids(target)

    return Response(
        {
            "checked": list(checked),
            "roles": [
                {
                    "id": role.pk,
                    "name": role.name,
                    "code": role.code,
                    # 界面上把「你授不出去的角色」标出来，而不是让人保存完
                    # 才发现少了几个。判断走 can_grant_role，不在前端重算。
                    "grantable": can_grant_role(request.user, role),
                }
                for role in Role.objects.filter(is_active=True).order_by("order_num", "id")
            ],
        }
    )
