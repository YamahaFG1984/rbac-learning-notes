from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.rbac.api.mixins import ScopedQuerysetMixin
from apps.tickets.export import tickets_csv_response
from apps.tickets.filters import apply_ticket_filters
from apps.tickets.models import Ticket
from apps.tickets.permissions import TicketPerm
from apps.tickets.services import get_assignable_users

from .serializers import AssigneeSerializer, TicketSerializer


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
        "assign": TicketPerm.ASSIGN,
        # 候选人列表是派单动作的一部分，用同一个权限点
        "assignable_users": TicketPerm.ASSIGN,
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

    @action(detail=False, url_path="assignable-users")
    def assignable_users(self, request):
        """派单候选人。

        ⚠️ 为什么不让前端去调 /api/v1/users/：
           那个接口要 system:user:view，而 cs_manager **只有** assign 权限。
           复用它等于强迫「能派单的人」都得有「用户管理」权限——
           权限点会被业务需求倒逼着变粗，这是权限模型腐化的典型路径。

        ⚠️ 权限用 ASSIGN 而不是新造一个 `ticket:ticket:view_assignee`：
           它不是一个独立的「界面上可点的东西」，只是派单这个动作的一部分。
           **权限点的粒度是动作，不是接口**（ADR-004）。
        """
        users = get_assignable_users(request.user)
        return Response(AssigneeSerializer(users, many=True).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """派单。

        ⚠️ get_object() 走的是 get_queryset()，也就是已经 .for_user() 过的
           queryset —— 范围外的工单在这里就 404 了，不需要再写一次判断。
        """
        ticket = self.get_object()

        assignee_id = request.data.get("assignee")
        # ⚠️ 候选人必须再校验一次。前端下拉框只列了范围内的人，
        #    但攻击者可以直接提交任意 id —— 下拉框不是安全边界，
        #    和「隐藏按钮不是安全边界」是同一句话。
        if assignee_id is not None and not get_assignable_users(request.user).filter(
            pk=assignee_id
        ).exists():
            raise ValidationError({"assignee": ["不在你可指派的范围内"]})

        ticket.assignee_id = assignee_id
        ticket.save(update_fields=["assignee", "updated_at"])
        return Response(self.get_serializer(ticket).data)

    def perform_create(self, serializer):
        # ⚠️ 必须**先**检查有没有部门，再赋值。
        #    department 是非空外键，赋 None 之后读 ticket.department
        #    抛的是 RelatedObjectDoesNotExist 而不是返回 None——
        #    非空外键的「空值」读取行为和普通字段不一样（同模板版 v0.13.0）。
        if self.request.user.department_id is None:
            raise ValidationError({"detail": "你尚未归属任何部门，无法创建工单"})
        serializer.save(
            creator=self.request.user, department=self.request.user.department
        )
