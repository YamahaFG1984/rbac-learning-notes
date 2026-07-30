from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.views import build_tree_rows

from .forms import DepartmentForm
from .models import Department


def department_list(request):
    rows = build_tree_rows(Department.objects.select_related("parent").all())
    return render(request, "accounts/department_list.html", {"rows": rows})


def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "部门已创建")
        return redirect("accounts:department_list")
    return render(
        request, "accounts/department_form.html", {"form": form, "title": "新建部门"}
    )


def department_update(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "部门已更新")
        return redirect("accounts:department_list")
    return render(
        request,
        "accounts/department_form.html",
        {"form": form, "title": f"编辑部门：{dept.name}"},
    )


@require_POST
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    try:
        dept.delete()
        messages.success(request, "部门已删除")
    except ProtectedError:
        # PROTECT 是数据库/ORM 层的约束，比在 delete() 里写检查更难被绕过。
        # 视图层只负责把它翻译成人话（FR-1.2 要求明确提示）。
        messages.error(request, f"「{dept.name}」下仍有子部门或在职用户，无法删除")
    return redirect("accounts:department_list")
