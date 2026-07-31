from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """必须继承 BaseUserAdmin。

    直接 admin.site.register(User) 的话，密码字段会变成明文输入框，
    admin 会把哈希串原样存进去，账号就废了。
    """

    fieldsets = BaseUserAdmin.fieldsets + (
        ("业务信息", {"fields": ("real_name", "phone", "department", "last_login_ip")}),
    )
    list_display = ("username", "real_name", "phone", "is_active", "is_superuser")
    search_fields = ("username", "real_name", "phone")

    def get_readonly_fields(self, request, obj=None):
        """⚠️ Django admin 是一个容易被忽略的后门。

        BaseUserAdmin 默认允许编辑 is_superuser / is_staff / user_permissions。
        任何拿到 is_staff 的人进了 admin 就能给自己提权——
        这绕过了我们在 Web 表单里做的全部白名单防护。

        非超管进 admin 时，把提权相关字段设为只读。
        （更彻底的做法是不给任何人 is_staff，本项目两道都做。）
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly += ["is_superuser", "is_staff", "user_permissions", "groups"]
        return readonly
