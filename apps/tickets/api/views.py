from rest_framework import viewsets

from apps.rbac.api.mixins import ScopedQuerysetMixin
from apps.tickets.models import Ticket
from apps.tickets.permissions import TicketPerm

from .serializers import TicketSerializer


class TicketViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    """工单 API。

    v1.2.0：功能权限（perm_map + HasPerm）+ 数据权限（ScopedQuerysetMixin）
    都接上了，且**没有重新实现任何判断逻辑**——全部复用 apps/rbac/services.py。
    """

    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("creator", "assignee", "department").all()
    perm_map = {
        "list": TicketPerm.VIEW,
        "retrieve": TicketPerm.VIEW,
        "create": TicketPerm.CREATE,
        "update": TicketPerm.UPDATE,
        "partial_update": TicketPerm.UPDATE,
        "destroy": TicketPerm.DELETE,
    }

    def perform_create(self, serializer):
        serializer.save(
            creator=self.request.user, department=self.request.user.department
        )
