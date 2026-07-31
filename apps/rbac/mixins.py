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
