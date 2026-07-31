from rest_framework import serializers

from apps.rbac.models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = [
            "id", "code", "name", "perm_type", "parent",
            "url_name", "icon", "is_visible", "is_active", "is_deprecated",
        ]


class RoleSerializer(serializers.ModelSerializer):
    inherits_from_name = serializers.CharField(source="inherits_from.name", read_only=True)
    data_scope_display = serializers.CharField(source="get_data_scope_display", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id", "code", "name", "description", "inherits_from", "inherits_from_name",
            "data_scope", "data_scope_display", "order_num", "is_builtin", "is_active",
        ]
        read_only_fields = ["is_builtin"]
