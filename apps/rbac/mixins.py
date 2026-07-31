"""类视图的权限 Mixin。

用法：class TicketListView(PermRequiredMixin, ListView)
      ⚠️ Mixin 必须排在前面，否则 super().dispatch() 链走不到它。
"""

from django.core.exceptions import PermissionDenied

from .services import user_has_any_perm, user_has_perm


class PermRequiredMixin:
    required_perm: str | None = None
    required_any_perms: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if self.required_perm and not user_has_perm(request.user, self.required_perm):
            raise PermissionDenied
        if self.required_any_perms and not user_has_any_perm(
            request.user, self.required_any_perms
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ScopedListMixin:
    """列表类视图的数据范围过滤。"""

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)


class ScopedObjectMixin:
    """单对象视图的数据范围约束。

    DRF 与 Django 的 get_object() 都走 get_queryset()，所以重写这一处
    就同时保护了详情 / 编辑（GET 和 POST）/ 删除——不会出现「只挡住 GET」
    的疏漏。用机制保证正确性，而不是靠每个视图都记得写。

    范围外的记录一律 404，不是 403：403 泄露了记录的存在性，
    攻击者可以遍历 ID 用 403/404 的差异画出数据库的 ID 分布。
    """

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)
