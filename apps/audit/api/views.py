from django.db.models import Q
from rest_framework import serializers, viewsets

from apps.audit.models import AuditLog
from apps.audit.permissions import AuditPerm


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    result_display = serializers.CharField(source="get_result_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_name", "action", "action_display",
            "target_type", "target_id", "target_repr", "detail",
            "ip", "result", "result_display", "created_at",
        ]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """审计日志只读。

    ⚠️ 用 ReadOnlyModelViewSet 而不是 ModelViewSet，是**第三道**防线：
       模型的 save()/delete() 挡单对象，AuditLogQuerySet 挡批量操作，
       这里挡 HTTP 入口。

       三道看起来冗余，但它们防的是不同的疏忽：
       前两道防「代码里写错」，这一道防「路由配错」——
       把 ModelViewSet 换成 ReadOnly 是一个词的事，
       而写成 ModelViewSet 时 DELETE 会一路走到 QuerySet 才被拦，
       用户看到的是 500 而不是 405。

    ⚠️ 审计日志**不做数据权限过滤**（没有 ScopedQuerysetMixin）。
       能看审计日志的人本来就是审计者，按部门切分反而会让
       「谁改了权限」这个问题查不出答案——审计的对象往往是管理员自己。
       所以门槛放在功能权限（system:audit:view）上，不放在数据范围上。
    """

    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor").all()
    perm_map = {"list": AuditPerm.VIEW, "retrieve": AuditPerm.VIEW}

    def filter_queryset(self, queryset):
        params = self.request.query_params
        if kw := params.get("kw", "").strip():
            queryset = queryset.filter(
                Q(actor_name__icontains=kw) | Q(target_repr__icontains=kw)
            )
        if action := params.get("action"):
            queryset = queryset.filter(action=action)
        return queryset
