from rest_framework import viewsets

from apps.accounts.models import Department, User
from apps.accounts.permissions import DeptPerm, UserPerm

from .serializers import DepartmentSerializer, UserSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """部门。

    ⚠️ 不分页（pagination_class = None）。

       部门是**树**，而树不能分页：客户端拿到第 1 页的 20 个节点去建树，
       第 21 个节点的父节点如果在第 2 页，整条分支就悄无声息地消失了。
       用户看到的是「少了几个部门」，没有任何报错。

       分页解决的是「数据太多」，但树形结构的正确性要求「一次拿全」。
       两者冲突时，先保证正确——部门数量级本来就不大（几十到几百）。
    """

    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    pagination_class = None
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
