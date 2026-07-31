from rest_framework import viewsets

from apps.rbac.models import Permission, Role

from .serializers import PermissionSerializer, RoleSerializer


class RoleViewSet(viewsets.ModelViewSet):
    """⚠️ v1.1.0：仅有认证，尚无授权。"""

    serializer_class = RoleSerializer
    queryset = Role.objects.select_related("inherits_from").all()


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """权限点只读——它由代码声明 + sync_permissions 同步，不允许 API 改（ADR-004）。"""

    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()
