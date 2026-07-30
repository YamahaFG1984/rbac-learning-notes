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
        ("业务信息", {"fields": ("real_name", "phone", "last_login_ip")}),
    )
    list_display = ("username", "real_name", "phone", "is_active", "is_superuser")
    search_fields = ("username", "real_name", "phone")
