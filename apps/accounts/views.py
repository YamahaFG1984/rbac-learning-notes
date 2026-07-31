from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.views import build_tree_rows
from apps.rbac.decorators import require_perm
from apps.rbac.models import Role
from apps.rbac.services import can_grant_role, get_user_role_ids, save_user_roles

from .forms import DepartmentForm, UserCreateForm, UserUpdateForm
from .models import Department, User
from .permissions import DeptPerm, UserPerm


@login_required
@require_perm(DeptPerm.VIEW)
def department_list(request):
    rows = build_tree_rows(Department.objects.select_related("parent").all())
    return render(request, "accounts/department_list.html", {"rows": rows})


@login_required
@require_perm(DeptPerm.CREATE)
def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "部门已创建")
        return redirect("accounts:department_list")
    return render(
        request, "accounts/department_form.html", {"form": form, "title": "新建部门"}
    )


@login_required
@require_perm(DeptPerm.UPDATE)
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


@login_required
@require_POST
@require_perm(DeptPerm.DELETE)
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


# --------------------------------------------------------------------------- #
# 用户管理（v0.6.0）
# --------------------------------------------------------------------------- #


@login_required
@require_perm(UserPerm.VIEW)
def user_list(request):
    users = User.objects.select_related("department").all()
    if kw := request.GET.get("kw", "").strip():
        users = users.filter(
            Q(username__icontains=kw) | Q(real_name__icontains=kw) | Q(phone__icontains=kw)
        )
    if dept_id := request.GET.get("dept"):
        dept = Department.objects.filter(pk=dept_id).first()
        if dept:
            users = users.filter(department__in=dept.get_descendants())

    paginator = Paginator(users, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page": page, "departments": Department.objects.all(), "kw": kw},
    )


@login_required
@require_perm(UserPerm.CREATE)
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"用户「{user}」已创建")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "title": "新建用户"})


@login_required
@require_perm(UserPerm.UPDATE)
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "用户已更新")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html", {"form": form, "title": f"编辑用户：{user}"}
    )


@login_required
@require_POST
@require_perm(UserPerm.DELETE)
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser:
        # 超管是逃生舱，不能从界面删掉（ADR-011）
        messages.error(request, "超级管理员不可从界面删除")
        return redirect("accounts:user_list")
    try:
        user.delete()
        messages.success(request, "用户已删除")
    except ProtectedError:
        messages.error(request, "该用户仍被其他数据引用，无法删除")
    return redirect("accounts:user_list")


@login_required
@require_perm(UserPerm.ASSIGN_ROLE)
def user_role_assign(request, pk):
    """给用户分配角色。角色数量少，多选 checkbox 即可。"""
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        ids = request.POST.getlist("roles")
        granter = request.user if request.user.is_authenticated else None
        # 权限不可放大：不能把自己不具备的角色授予他人（ADR-011）
        allowed, refused = [], []
        for role in Role.objects.filter(id__in=ids):
            (allowed if can_grant_role(granter, role) else refused).append(role.pk)
        if refused:
            messages.warning(
                request,
                f"已忽略 {len(refused)} 个超出你自身权限范围的角色",
            )
        saved = save_user_roles(user, allowed, granted_by=granter)
        messages.success(request, f"已为「{user}」分配 {len(saved)} 个角色")
        return redirect("accounts:user_list")

    checked = get_user_role_ids(user)
    roles = Role.objects.filter(is_active=True)
    return render(
        request,
        "accounts/user_role_assign.html",
        {"target_user": user, "roles": roles, "checked": checked},
    )
