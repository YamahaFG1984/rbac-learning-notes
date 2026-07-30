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
        fields = [
            "code",
            "name",
            "description",
            "inherits_from",
            "data_scope",
            "order_num",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_CLS}),
            "name": forms.TextInput(attrs={"class": INPUT_CLS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLS, "rows": 3}),
            "inherits_from": forms.Select(attrs={"class": INPUT_CLS}),
            "data_scope": forms.Select(attrs={"class": INPUT_CLS}),
            "order_num": forms.NumberInput(attrs={"class": INPUT_CLS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_scope"].help_text = "⚠️ 数据范围在 v0.14.0 才生效"

        qs = Role.objects.all()
        if self.instance.pk:
            # 排除自身及其所有后代——能不给用户选择错误选项的机会，
            # 就不要让他选完再报错。clean() 里的环检测是兜底，不是第一道防线。
            qs = qs.exclude(pk__in=_descendant_ids(self.instance))
        self.fields["inherits_from"].queryset = qs
        self.fields["inherits_from"].empty_label = "（不继承）"


def _descendant_ids(role):
    """角色的自身 + 全部后代 ID。

    Role 没有 path 字段（不像 Department），只能沿 inheritors 反向遍历。
    角色数量少，逐层展开可以接受。
    """
    ids = {role.pk}
    frontier = [role.pk]
    while frontier:
        children = list(
            Role.objects.filter(inherits_from_id__in=frontier)
            .exclude(pk__in=ids)
            .values_list("pk", flat=True)
        )
        if not children:
            break
        ids.update(children)
        frontier = children
    return ids
