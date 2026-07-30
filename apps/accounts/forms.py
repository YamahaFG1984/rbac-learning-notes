from django import forms

from .models import Department

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
