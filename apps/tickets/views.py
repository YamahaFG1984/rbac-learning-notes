import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.rbac.decorators import require_perm

from .constants import Priority, Status
from .forms import TicketAssignForm, TicketForm
from .models import Ticket
from .permissions import TicketPerm


def _base_queryset(user):
    """业务查询的统一入口。

    .for_user() 必须**显式**调用——这样你能通过 grep 找出所有
    绕过数据权限的查询（ADR-009）。
    """
    return Ticket.objects.select_related("creator", "assignee", "department").for_user(
        user
    )


@login_required
@require_perm(TicketPerm.VIEW)
def ticket_list(request):
    qs = _base_queryset(request.user)

    kw = request.GET.get("kw", "").strip()
    if kw:
        qs = qs.filter(Q(title__icontains=kw) | Q(content__icontains=kw))
    if status := request.GET.get("status"):
        qs = qs.filter(status=status)
    if priority := request.GET.get("priority"):
        qs = qs.filter(priority=priority)

    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "tickets/list.html",
        {
            "page": page,
            "kw": kw,
            "statuses": Status.choices,
            "priorities": Priority.choices,
        },
    )


@login_required
@require_perm(TicketPerm.VIEW)
def ticket_detail(request, pk):
    ticket = get_object_or_404(_base_queryset(request.user), pk=pk)
    return render(request, "tickets/detail.html", {"ticket": ticket})


@login_required
@require_perm(TicketPerm.CREATE)
def ticket_create(request):
    form = TicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.creator = request.user
        ticket.department = request.user.department  # 快照，见模型注释
        if ticket.department is None:
            messages.error(request, "你尚未归属任何部门，无法创建工单")
            return redirect("tickets:list")
        ticket.save()
        messages.success(request, "工单已创建")
        return redirect("tickets:list")
    return render(request, "tickets/form.html", {"form": form, "title": "新建工单"})


@login_required
@require_perm(TicketPerm.UPDATE)
def ticket_update(request, pk):
    # ✅ 唯一正确的写法：范围内找得到就正常，找不到就 404。
    #    一行代码同时解决了「存在性」和「权限」两件事。
    #
    # ❌ 错误写法（IDOR 漏洞的标准形态）：
    #        ticket = get_object_or_404(Ticket, pk=pk)
    #        if ticket.department != request.user.department: raise PermissionDenied
    #    两个问题：一是重复实现了范围判断，和 build_scope_q 的规则迟早不一致；
    #    二是 403 泄露了记录的存在性。
    #
    # ⚠️ 注意这里同时覆盖了 GET 和 POST——只挡住 GET 是很常见的疏漏，
    #    攻击者直接构造 POST 就绕过了。
    ticket = get_object_or_404(_base_queryset(request.user), pk=pk)
    form = TicketForm(request.POST or None, instance=ticket)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "工单已更新")
        return redirect("tickets:list")
    return render(
        request, "tickets/form.html", {"form": form, "title": f"编辑工单：{ticket.title}"}
    )


@login_required
@require_POST
@require_perm(TicketPerm.DELETE)
def ticket_delete(request, pk):
    ticket = get_object_or_404(_base_queryset(request.user), pk=pk)
    ticket.delete()
    messages.success(request, "工单已删除")
    return redirect("tickets:list")


@login_required
@require_perm(TicketPerm.ASSIGN)
def ticket_assign(request, pk):
    ticket = get_object_or_404(_base_queryset(request.user), pk=pk)
    form = TicketAssignForm(request.POST or None, instance=ticket)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "已派单")
        return redirect("tickets:list")
    return render(
        request, "tickets/form.html", {"form": form, "title": f"派单：{ticket.title}"}
    )


@login_required
@require_perm(TicketPerm.EXPORT)
def ticket_export(request):
    """导出 CSV。

    走**同一个** _base_queryset(request.user)——导出是最容易被忽略的
    越权入口，因为它通常是后加的功能，代码路径也和列表页不同。
    验收标准：导出的行数 == 列表页显示的总数。
    """
    qs = _base_queryset(request.user)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="tickets.csv"'
    writer = csv.writer(response)
    writer.writerow(["ID", "标题", "状态", "优先级", "创建人", "归属部门", "处理人", "创建时间"])
    for t in qs.iterator():
        writer.writerow(
            [
                t.id,
                t.title,
                t.get_status_display(),
                t.get_priority_display(),
                str(t.creator),
                t.department.name,
                str(t.assignee) if t.assignee else "",
                t.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return response
