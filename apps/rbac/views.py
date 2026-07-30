from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from apps.common.views import build_tree_rows

from .decorators import require_perm

from .forms import RoleForm
from .permissions import PermPerm, RolePerm
from .models import Permission, Role
from .services import get_role_permission_ids, save_role_permissions


@login_required
@require_perm(PermPerm.VIEW)
def permission_list(request):
    rows = build_tree_rows(Permission.objects.select_related("parent").all())
    return render(request, "rbac/permission_list.html", {"rows": rows})


@login_required
@require_perm(RolePerm.VIEW)
def role_list(request):
    roles = Role.objects.all()
    return render(request, "rbac/role_list.html", {"roles": roles})


@login_required
@require_perm(RolePerm.CREATE)
def role_create(request):
    form = RoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        role = form.save()
        messages.success(request, f"角色「{role.name}」已创建")
        return redirect("rbac:role_list")
    return render(request, "rbac/role_form.html", {"form": form, "title": "新建角色"})


@login_required
@require_perm(RolePerm.UPDATE)
def role_update(request, pk):
    role = get_object_or_404(Role, pk=pk)
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "角色已更新")
        return redirect("rbac:role_list")
    return render(
        request, "rbac/role_form.html", {"form": form, "title": f"编辑角色：{role.name}"}
    )


@login_required
@require_POST
@require_perm(RolePerm.DELETE)
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    try:
        role.delete()
        messages.success(request, "角色已删除")
    except RuntimeError as exc:
        messages.error(request, str(exc))
    except ProtectedError:
        messages.error(request, f"角色「{role.name}」仍被引用，无法删除")
    return redirect("rbac:role_list")


@login_required
@require_perm(RolePerm.ASSIGN_PERM)
def role_perm_assign(request, pk):
    """角色权限配置：一棵树，勾选即可。"""
    role = get_object_or_404(Role, pk=pk)

    if request.method == "POST":
        ids = request.POST.getlist("permissions")
        saved = save_role_permissions(role, ids)
        messages.success(request, f"已保存 {len(saved)} 项权限")
        return redirect("rbac:role_list")

    perms = Permission.objects.filter(is_active=True, is_deprecated=False)
    checked = get_role_permission_ids(role)
    rows = build_tree_rows(perms)
    for row in rows:
        row["checked"] = row["obj"].pk in checked

    return render(request, "rbac/role_perm_assign.html", {"role": role, "rows": rows})
