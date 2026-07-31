from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.rbac.decorators import require_perm

from .constants import AuditAction
from .models import AuditLog
from .permissions import AuditPerm


@login_required
@require_perm(AuditPerm.VIEW)
def log_list(request):
    qs = AuditLog.objects.select_related("actor").all()

    if kw := request.GET.get("kw", "").strip():
        qs = qs.filter(Q(actor_name__icontains=kw) | Q(target_repr__icontains=kw))
    if action := request.GET.get("action"):
        qs = qs.filter(action=action)

    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/log_list.html",
        {"page": page, "kw": kw, "actions": AuditAction.choices},
    )
