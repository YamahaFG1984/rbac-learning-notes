from django import forms

from apps.accounts.forms import INPUT_CLS

from .models import Ticket


class TicketForm(forms.ModelForm):
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
    class Meta:
        model = Ticket
        fields = ["assignee"]
        widgets = {"assignee": forms.Select(attrs={"class": INPUT_CLS})}
