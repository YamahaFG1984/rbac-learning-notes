from rest_framework import serializers

from apps.tickets.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.real_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "title", "content", "priority", "status", "status_display",
            "creator", "creator_name", "assignee", "department", "department_name",
            "created_at", "updated_at",
        ]
        # creator / department 由服务端从 request.user 快照，
        # 允许客户端提交就等于允许伪造创建人（同 v0.13.0 的表单）
        read_only_fields = ["creator", "department", "created_at", "updated_at"]
