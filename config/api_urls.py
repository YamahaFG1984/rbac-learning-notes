"""API 路由（v1.1.0）。

与 Web 路由**并存**——同一套业务逻辑、同一套权限内核，
服务两种完全不同的表现层。
"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.api.views import DepartmentViewSet, UserViewSet
from apps.audit.api.views import AuditLogViewSet
from apps.rbac.api import admin_views
from apps.rbac.api.auth_views import csrf, login_view, logout_view
from apps.rbac.api.views import PermissionViewSet, RoleViewSet, health, profile
from apps.tickets.api.views import TicketViewSet

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("tickets", TicketViewSet, basename="ticket")
router.register("audit-logs", AuditLogViewSet, basename="auditlog")

app_name = "api"

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", profile, name="profile"),
    path("auth/csrf/", csrf, name="csrf"),
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    # 角色/用户的权限配置。刻意用函数视图而不是 ViewSet 的 @action：
    # 它们是「配置」不是「资源」，硬套 REST 反而要造出
    # /roles/1/permissions/ 这种既不是集合也不是单例的东西
    path("roles/<int:pk>/permissions/", admin_views.role_permissions, name="role_perms"),
    path(
        "roles/<int:pk>/effective-permissions/",
        admin_views.role_effective_permissions,
        name="role_effective_perms",
    ),
    path("roles/<int:pk>/data-scope/", admin_views.role_data_scope, name="role_scope"),
    path("users/<int:pk>/roles/", admin_views.user_roles, name="user_roles"),
    *router.urls,
]
