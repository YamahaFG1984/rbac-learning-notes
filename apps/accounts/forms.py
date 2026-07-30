from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Department, User

# 写完整的类名字符串——Tailwind 是静态扫描，拼接出来的 class 名它看不见
INPUT_CLS = (
    "block w-full rounded-md border-0 px-2 py-1.5 text-sm text-gray-900 "
    "ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600"
)


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        # 白名单：新增字段默认不进表单，要加必须显式写一行（CLAUDE.md 安全红线 3）
        fields = ["code", "name", "parent", "order_num", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_CLS}),
            "name": forms.TextInput(attrs={"class": INPUT_CLS}),
            "parent": forms.Select(attrs={"class": INPUT_CLS}),
            "order_num": forms.NumberInput(attrs={"class": INPUT_CLS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Department.objects.all()
        if self.instance.pk:
            # 排除自身及其后代，不给用户选出环的机会
            qs = qs.exclude(path__startswith=self.instance.path)
        self.fields["parent"].queryset = qs
        self.fields["parent"].empty_label = "（作为顶级部门）"


# ⚠️ 用户表单一律用白名单 fields，绝不用黑名单 exclude。
#    黑名单是随时间自然劣化的设计：将来给 User 加了新的敏感字段，
#    它会自动出现在表单里，没有任何人会注意到。
#    白名单相反：新字段默认不在表单里，要加必须显式写一行，那行会进 code review。
#
#    尤其是 is_superuser——如果它出现在这里，任何拥有 system:user:update
#    权限的人都能把自己提升为超管。超管只能通过 createsuperuser 创建（ADR-011）。
_USER_FIELDS = ["username", "real_name", "phone", "email", "department", "is_active"]

_USER_WIDGETS = {
    "username": forms.TextInput(attrs={"class": INPUT_CLS}),
    "real_name": forms.TextInput(attrs={"class": INPUT_CLS}),
    "phone": forms.TextInput(attrs={"class": INPUT_CLS}),
    "email": forms.EmailInput(attrs={"class": INPUT_CLS}),
    "department": forms.Select(attrs={"class": INPUT_CLS}),
}


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = _USER_FIELDS
        widgets = _USER_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs["class"] = INPUT_CLS


class UserUpdateForm(forms.ModelForm):
    """编辑用户。不含密码——改密码走独立的重置入口（FR-1.6）。"""

    class Meta:
        model = User
        fields = _USER_FIELDS
        widgets = _USER_WIDGETS
