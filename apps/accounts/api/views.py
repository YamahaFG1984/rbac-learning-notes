from rest_framework import viewsets

from apps.accounts.models import Department, User
from apps.accounts.permissions import DeptPerm, UserPerm

from .serializers import DepartmentSerializer, UserSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    perm_map = {
        "list": DeptPerm.VIEW,
        "retrieve": DeptPerm.VIEW,
        "create": DeptPerm.CREATE,
        "update": DeptPerm.UPDATE,
        "partial_update": DeptPerm.UPDATE,
        "destroy": DeptPerm.DELETE,
    }


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.select_related("department").all()
    perm_map = {
        "list": UserPerm.VIEW,
        "retrieve": UserPerm.VIEW,
        "create": UserPerm.CREATE,
        "update": UserPerm.UPDATE,
        "partial_update": UserPerm.UPDATE,
        "destroy": UserPerm.DELETE,
    }
