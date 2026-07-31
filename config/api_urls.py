"""API 路由（v1.1.0）。

与 Web 路由**并存**——同一套业务逻辑、同一套权限内核，
服务两种完全不同的表现层。
"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.api.views import DepartmentViewSet, UserViewSet
from apps.rbac.api.views import PermissionViewSet, RoleViewSet, profile
from apps.tickets.api.views import TicketViewSet

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("tickets", TicketViewSet, basename="ticket")

app_name = "api"

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", profile, name="profile"),
    *router.urls,
]
