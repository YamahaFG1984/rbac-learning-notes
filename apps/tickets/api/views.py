from rest_framework import viewsets
from rest_framework.decorators import action

from apps.rbac.api.mixins import ScopedQuerysetMixin
from apps.tickets.export import tickets_csv_response
from apps.tickets.filters import apply_ticket_filters
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
        # ⚠️ 加了 action 就必须加这一行。忘了的话 rbac.W002 会在 check 阶段报警——
        # 「新加的接口忘了声明权限」是最常见的越权成因。
        "export": TicketPerm.EXPORT,
    }

    def filter_queryset(self, queryset):
        """业务筛选。

        ⚠️ 和模板版共用 apply_ticket_filters —— 两边筛得不一样的话，
           同一个用户在两个前端会看到不同的条数，而两边的**权限**都是对的，
           这种 bug 极难定位。

        ⚠️ 权限过滤不在这里，在 get_queryset()（ScopedQuerysetMixin）。
           DRF 的调用顺序是 get_queryset() → filter_queryset()，
           所以进到这里的 queryset 已经是 .for_user() 过的了。
           **绝不要把两者写进同一个函数**：混在一起之后，
           任何人加一个业务筛选都可能顺手改坏权限过滤。
        """
        return apply_ticket_filters(queryset, self.request.query_params)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """导出 CSV。

        走**同一条** get_queryset() + filter_queryset() 链路——
        导出是最容易被忽略的越权入口，因为它通常是后加的，
        代码路径也和列表页不同。

        验收标准：导出的行数 == 列表页的 count。
        """
        qs = self.filter_queryset(self.get_queryset())
        return tickets_csv_response(qs)

    def perform_create(self, serializer):
        serializer.save(
            creator=self.request.user, department=self.request.user.department
        )
