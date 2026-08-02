from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from apps.common.views import build_tree_rows

from .decorators import require_perm

from .forms import RoleForm
from .perm_tree import annotate_role_perm_rows, has_inherited
from .scope_config import save_role_scope
from .permissions import PermPerm, RolePerm
from apps.accounts.models import Department
from apps.common.views import build_tree_rows as _btr

from .models import Permission, Role
from .services import (
    filter_grantable_permission_ids,
    get_role_department_ids,
    get_role_effective_codes,
    get_role_perm_sources,
    get_role_permission_ids,
    save_role_departments,
    save_role_permissions,
)


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
        # 权限不可放大：不能授出自己不具备的权限（ADR-011）
        kept, rejected = filter_grantable_permission_ids(
            request.user, ids, existing_ids=get_role_permission_ids(role)
        )
        saved = save_role_permissions(role, kept, actor=request.user)
        if rejected:
            messages.warning(
                request,
                f"已忽略 {len(rejected)} 项你自己不具备的权限——不能授出自己没有的权限",
            )
        messages.success(request, f"已保存 {len(saved)} 项权限")
        return redirect("rbac:role_list")

    perms = Permission.objects.filter(is_active=True, is_deprecated=False)

    # v1.3.0：checked / inherited 的计算抽到 perm_tree.py，与 SPA 共用。
    # 继承来的权限以灰色只读勾选显示，与直接授予的视觉区分。
    # 不能在子角色里取消一个继承来的权限——那需要「负权限」，本项目不做。
    rows = annotate_role_perm_rows(role, build_tree_rows(perms))

    return render(
        request,
        "rbac/role_perm_assign.html",
        {"role": role, "rows": rows, "has_inherited": has_inherited(role)},
    )


@login_required
@require_perm(RolePerm.VIEW)
def role_effective_perms(request, pk):
    """查看角色展开继承后的完整权限，并标注每个权限来自哪个角色。

    这个页面看起来是锦上添花，实际是**运维刚需**：
    有人问「为什么张三能删工单」，你必须能在 10 秒内回答。
    """
    role = get_object_or_404(Role, pk=pk)
    sources = get_role_perm_sources(role)
    perms = {
        p.code: p
        for p in Permission.objects.filter(code__in=sources.keys(), is_active=True)
    }
    rows = sorted(
        (
            {
                "code": code,
                "name": perms[code].name if code in perms else code,
                "source": src,
                "is_direct": src.pk == role.pk,
            }
            for code, src in sources.items()
        ),
        key=lambda r: r["code"],
    )
    chain = []
    current, depth = role, 0
    while current is not None and depth <= 6:
        chain.append(current)
        current = current.inherits_from
        depth += 1
    return render(
        request,
        "rbac/role_effective_perms.html",
        {"role": role, "rows": rows, "chain": chain},
    )


@login_required
@require_perm(RolePerm.ASSIGN_PERM)
def role_data_scope(request, pk):
    """配置角色的数据范围。选「自定义部门」时才勾选部门树。"""
    role = get_object_or_404(Role, pk=pk)

    if request.method == "POST":
        # v1.3.0：保存逻辑（含审计信号）抽到 scope_config.py，与 SPA 共用。
        # 各写一遍的话很可能只有一边记了日志，而缺失的那边正好是会被利用的那边。
        save_role_scope(
            role,
            request.POST.get("data_scope", role.data_scope),
            request.POST.getlist("departments"),
            actor=request.user,
        )
        messages.success(request, "数据范围已更新")
        return redirect("rbac:role_list")

    checked = get_role_department_ids(role)
    rows = _btr(Department.objects.all())
    for row in rows:
        row["checked"] = row["obj"].pk in checked

    from .constants import DataScope

    return render(
        request,
        "rbac/role_data_scope.html",
        {"role": role, "rows": rows, "scopes": DataScope.choices, "custom": DataScope.CUSTOM},
    )
