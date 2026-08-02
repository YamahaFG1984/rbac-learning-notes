from django import forms

from apps.accounts.forms import INPUT_CLS
from apps.accounts.models import User

from .models import Ticket
from .services import get_assignable_users


class TicketForm(forms.ModelForm):
    """新建 / 编辑工单。

    ⚠️ 和 TicketAssignForm 同一个问题：assignee 是外键下拉框，
       不限制的话，只有 ticket:ticket:create 的 cs_staff
       也能看到全公司的用户名册。
    """

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        # ⚠️ 忘了传 actor 时兜底为**空集**，不是全部用户。
        #    「出错时的默认值必须指向后果最轻的方向」——退回全集
        #    就是退回 v0.15.0 的那个泄露，而且悄无声息。
        #    空下拉框会立刻被发现，全量下拉框不会。
        self.fields["assignee"].queryset = (
            get_assignable_users(actor) if actor is not None else User.objects.none()
        )

    class Meta:
        model = Ticket
        # ⚠️ 白名单，且 creator / department 绝不在其中——
        #    它们由视图从 request.user 快照，允许用户提交就等于允许伪造创建人。
        fields = ["title", "content", "priority", "status", "assignee"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLS}),
            "content": forms.Textarea(attrs={"class": INPUT_CLS, "rows": 5}),
            "priority": forms.Select(attrs={"class": INPUT_CLS}),
            "status": forms.Select(attrs={"class": INPUT_CLS}),
            "assignee": forms.Select(attrs={"class": INPUT_CLS}),
        }


class TicketAssignForm(forms.ModelForm):
    """派单。

    ⚠️ 必须传 actor —— 否则 ModelForm 会用**全部用户**当候选人。
       v0.15.0 就是这么写的，结果是没有 system:user:view 的人
       通过这个下拉框看到了完整的用户名册（见 services.get_assignable_users）。

       ModelForm 的默认行为是「这个外键指向的所有对象」，它对权限一无所知。
       **凡是外键下拉框，都要问一句「这个列表该给谁看」。**
    """

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        # ⚠️ 忘了传 actor 时兜底为**空集**，不是全部用户。
        #    「出错时的默认值必须指向后果最轻的方向」——退回全集
        #    就是退回 v0.15.0 的那个泄露，而且悄无声息。
        #    空下拉框会立刻被发现，全量下拉框不会。
        self.fields["assignee"].queryset = (
            get_assignable_users(actor) if actor is not None else User.objects.none()
        )

    class Meta:
        model = Ticket
        fields = ["assignee"]
        widgets = {"assignee": forms.Select(attrs={"class": INPUT_CLS})}
