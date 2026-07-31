from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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
@permission_classes([IsAuthenticated])
def profile(request):
    """当前用户的信息 + 权限码 + 菜单树。

    前端拿到这个才能渲染路由和菜单。

    ⚠️ 注意 get_user_perm_codes / get_user_menu_tree 就是模板层用的
       **同一个函数**——不是「API 版本」，是同一个（ADR-013）。

       get_user_menu_tree 在 v0.11.0 就被要求返回 list[dict] 而不是
       model 实例，伏笔在这里：直接就能 JSON 序列化。
    """
    user = request.user
    codes = get_user_perm_codes(user)
    return Response(
        {
            "user": {
                "id": user.pk,
                "username": user.username,
                "real_name": user.real_name,
                "department": (
                    {"id": user.department_id, "name": user.department.name}
                    if user.department_id
                    else None
                ),
                "is_superuser": user.is_superuser,
            },
            # 超管的 ALL_PERMS 哨兵不可序列化，用 ["*"] 表示「全部放行」，
            # 前端据此跳过逐码判断。这一点必须和前端约定好。
            "perms": ["*"] if user.is_superuser else sorted(codes),
            "menus": get_user_menu_tree(user),
        }
    )
