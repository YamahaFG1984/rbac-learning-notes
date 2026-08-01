from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.rbac.models import Permission, Role
from apps.rbac.permissions import PermPerm, RolePerm
from apps.rbac.services import get_user_menu_tree, get_user_perm_codes

from .serializers import PermissionSerializer, RoleSerializer


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    queryset = Role.objects.select_related("inherits_from").all()
    perm_map = {
        "list": RolePerm.VIEW,
        "retrieve": RolePerm.VIEW,
        "create": RolePerm.CREATE,
        "update": RolePerm.UPDATE,
        "partial_update": RolePerm.UPDATE,
        "destroy": RolePerm.DELETE,
    }


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """权限点只读——它由代码声明 + sync_permissions 同步，不允许 API 改（ADR-004）。"""

    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()
    perm_map = {"list": PermPerm.VIEW, "retrieve": PermPerm.VIEW}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """连通性探针。

    刻意不需要认证——前端用它验证同域代理是否打通（fe-v0.1.0）。
    不返回任何业务信息。
    """
    return Response({"detail": "ok"})


def _enrich_menus_for_spa(nodes, extra):
    """给菜单树补上前端路由字段。

    ⚠️ 刻意放在 API 层而不是 services.get_user_menu_tree() 里。

       route_path / component 是**这一种表现层**特有的东西，模板版完全用不上。
       把它们塞进内核，就是让内核认识 React——那正是 ADR-013 要防的。

       更省事的做法当然是直接改 get_user_menu_tree() 多输出两个字段，
       但那等于承认「内核可以为某个前端多输出字段」：
       今天加 React 的两个，明天加小程序的三个，内核就慢慢变成了
       所有前端的公共字段袋。

       约束的价值在于它被坚持时才存在。破例一次，后面每次都能找到破例的理由。
    """
    for node in nodes:
        meta = extra.get(node["id"], {})
        node["routePath"] = meta.get("route_path") or None
        node["component"] = meta.get("component") or None
        _enrich_menus_for_spa(node["children"], extra)
    return nodes


def build_profile_payload(user):
    """当前用户的信息 + 权限码 + 菜单树。

    ⚠️ get_user_perm_codes / get_user_menu_tree 就是模板层用的**同一个函数**
       ——不是「API 版本」，是同一个（ADR-013）。
    """
    codes = get_user_perm_codes(user)
    return {
        "user": {
            "id": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "department": (
                {"id": user.department_id, "name": user.department.name}
                if user.department_id
                else None
            ),
            "isSuperuser": user.is_superuser,
        },
        # 超管的 ALL_PERMS 哨兵不可序列化，用 ["*"] 表示「全部放行」，
        # 前端据此跳过逐码判断。这一点必须和前端约定好。
        "perms": ["*"] if user.is_superuser else sorted(codes),
        "menus": _enrich_menus_for_spa(
            get_user_menu_tree(user),  # ← 内核原样调用，一行不改
            {
                row["id"]: row
                for row in Permission.objects.filter(is_active=True).values(
                    "id", "route_path", "component"
                )
            },
        ),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile(request):
    """当前用户的信息 + 权限码 + 菜单树。

    前端拿到这个才能渲染路由和菜单。

    ⚠️ 注意 get_user_perm_codes / get_user_menu_tree 就是模板层用的
       **同一个函数**——不是「API 版本」，是同一个（ADR-013）。

       get_user_menu_tree 在 v0.11.0 就被要求返回 list[dict] 而不是
       model 实例，伏笔在这里：直接就能 JSON 序列化。
    """
    return Response(build_profile_payload(request.user))
