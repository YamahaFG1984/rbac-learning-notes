from rest_framework import viewsets

from apps.tickets.models import Ticket

from .serializers import TicketSerializer


class TicketViewSet(viewsets.ModelViewSet):
    """工单 API。

    ⚠️ v1.1.0：仅有认证（IsAuthenticated），尚无功能权限和数据权限。
       任何登录用户都能调用全部接口——包括删除别人部门的工单。

       这是刻意留下的中间态。Web 层花了 11 个 tag 建立的权限体系，
       在 API 层一个都没生效——这正是很多真实项目的失败模式：
       为了对接前端/小程序加了一套 API，而 API 走的是另一条代码路径。

       v1.2.0 会补上，且**不重新实现任何判断逻辑**。
    """

    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("creator", "assignee", "department").all()

    def perform_create(self, serializer):
        serializer.save(
            creator=self.request.user, department=self.request.user.department
        )
