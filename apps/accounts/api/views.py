from rest_framework import viewsets

from apps.accounts.models import Department, User

from .serializers import DepartmentSerializer, UserSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """⚠️ v1.1.0：仅有认证（IsAuthenticated），尚无功能权限和数据权限。
    任何登录用户都能调用全部接口——刻意留下的中间态，v1.2.0 补上。"""

    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()


class UserViewSet(viewsets.ModelViewSet):
    """⚠️ 同上，v1.1.0 尚无授权。"""

    serializer_class = UserSerializer
    queryset = User.objects.select_related("department").all()
