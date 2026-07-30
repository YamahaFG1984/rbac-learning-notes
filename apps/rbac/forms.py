from django import forms

from .models import Role

# 写完整的类名字符串——Tailwind 是静态扫描，拼接出来的 class 名它看不见
INPUT_CLS = (
    "block w-full rounded-md border-0 px-2 py-1.5 text-sm text-gray-900 "
    "ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600"
)


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        # 白名单：新增字段默认不进表单（CLAUDE.md 安全红线 3）。
        # is_builtin 刻意不在此列——它只能由 seed / 迁移设置，不能从界面改。
        fields = ["code", "name", "description", "data_scope", "order_num", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_CLS}),
            "name": forms.TextInput(attrs={"class": INPUT_CLS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLS, "rows": 3}),
            "data_scope": forms.Select(attrs={"class": INPUT_CLS}),
            "order_num": forms.NumberInput(attrs={"class": INPUT_CLS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_scope"].help_text = "⚠️ 数据范围在 v0.14.0 才生效"
