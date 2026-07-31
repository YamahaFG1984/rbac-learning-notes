from rest_framework import serializers

from apps.accounts.models import Department, User


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        # ⚠️ 白名单。fields = "__all__" 是最危险的写法——
        #    它会把将来新增的任何字段自动暴露出去（同 v0.18.0 表单白名单的道理，
        #    而 API 的风险更大：Web 表单至少还有个界面，API 是直接暴露的）。
        fields = ["id", "code", "name", "parent", "path", "depth", "order_num", "is_active"]
        read_only_fields = ["path", "depth"]


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = User
        # 绝不包含 password / is_superuser / is_staff / user_permissions / groups
        fields = [
            "id", "username", "real_name", "phone", "email",
            "department", "department_name", "is_active", "date_joined",
        ]
        read_only_fields = ["date_joined"]
