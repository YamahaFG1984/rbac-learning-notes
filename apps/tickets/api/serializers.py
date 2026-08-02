from rest_framework import serializers

from apps.tickets.models import Ticket


class AssigneeSerializer(serializers.Serializer):
    """派单候选人。

    ⚠️ 刻意**不复用** accounts 的 UserSerializer。

       那个 serializer 带 phone / email / is_active / date_joined，
       而这里的调用方只需要「显示一个名字、提交一个 id」。
       复用会让一个只有 ticket:ticket:assign 的人拿到用户的手机号和邮箱——
       通过一个下拉框接口。

       **接口返回的字段量，应该由调用方的需要决定，不是由「手边有什么」决定。**
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    real_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=""
    )


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
