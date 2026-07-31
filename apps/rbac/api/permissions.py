"""DRF 权限类。

⚠️ 本文件不包含任何权限判断逻辑——它只是把 DRF 的调用约定翻译成
   对统一内核 services.user_has_perm() 的调用。

   Web 层的 @require_perm 装饰器做的是同一件事（ADR-013）。
   两套逻辑必然漂移，漂移处就是漏洞。
"""

from rest_framework.permissions import BasePermission

from apps.rbac.services import user_has_perm


class HasPerm(BasePermission):
    """基于 view.perm_map 的功能权限校验。

    perm_map 把 DRF 的 action 映射到权限码：

        perm_map = {
            "list": TicketPerm.VIEW,
            "destroy": TicketPerm.DELETE,
            ...
        }

    ⚠️ **漏配 = 拒绝，不是放行**。

       写成「没配就放行」的话，加了一个自定义 @action 却忘了配 perm_map，
       那个接口就裸奔了——而且是静默的。自定义 action 是漏配的重灾区，
       因为它们不在标准 CRUD 列表里。

       默认拒绝需要机制保证（同 v0.9.0 的 rbac.W001）。
    """

    message = "权限不足"

    def has_permission(self, request, view):
        perm_map = getattr(view, "perm_map", None)
        if perm_map is None:
            # 该 view 完全不受权限管控——必须显式声明（见 rbac.W002 自检）
            return True

        action = getattr(view, "action", None)
        if action is None:
            return True  # 非 ViewSet（如 APIView），由它自己声明

        if action not in perm_map:
            return False  # 漏配 -> 403，而不是静默放行

        code = perm_map[action]
        return code is None or user_has_perm(request.user, code)
