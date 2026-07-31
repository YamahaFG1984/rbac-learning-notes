"""垂直越权：获得比自己更高级别的权限。"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import (
    can_grant_role,
    filter_grantable_permission_ids,
    get_user_perm_codes,
)


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def make_role(code, *codes):
    role = Role.objects.create(code=code, name=code)
    for c in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=c))
    return role


def fresh(user):
    return type(user).objects.get(pk=user.pk)


@pytest.fixture
def attacker(django_user_model, perms):
    """一个「权限管理员」：能改用户、能配角色权限，但没有部门删除权。"""
    user = django_user_model.objects.create_user(username="attacker", password="x")
    role = make_role(
        "perm_admin",
        "system:user:view",
        "system:user:update",
        "system:user:assign_role",
        "system:role:view",
        "system:role:assign_perm",
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
class TestSuperuserFlagProtection:
    def test_cannot_set_is_superuser_via_form_post(self, client, attacker):
        """表单用白名单 fields 而非黑名单 exclude。

        黑名单是随时间自然劣化的设计：将来加了新的敏感字段，
        它会自动出现在表单里，没有任何人会注意到。
        """
        client.force_login(attacker)
        client.post(
            reverse("accounts:user_update", args=[attacker.pk]),
            {
                "username": "attacker",
                "real_name": "x",
                "is_active": "1",
                "is_superuser": "1",  # ← 硬塞
                "is_staff": "1",
            },
        )
        attacker.refresh_from_db()
        assert attacker.is_superuser is False
        assert attacker.is_staff is False

    def test_form_field_whitelist_excludes_sensitive_fields(self):
        from apps.accounts.forms import UserCreateForm, UserUpdateForm

        for form_cls in (UserCreateForm, UserUpdateForm):
            fields = set(form_cls().fields)
            assert "is_superuser" not in fields
            assert "is_staff" not in fields
            assert "user_permissions" not in fields
            assert "groups" not in fields

    def test_admin_readonly_for_non_superuser(self, rf, attacker, django_user_model):
        """⚠️ Django admin 是容易被忽略的后门。

        BaseUserAdmin 默认允许编辑 is_superuser——任何拿到 is_staff 的人
        进了 admin 就能给自己提权，绕过 Web 表单的全部白名单防护。
        """
        from django.contrib.admin.sites import AdminSite

        from apps.accounts.admin import UserAdmin
        from apps.accounts.models import User

        admin = UserAdmin(User, AdminSite())

        req = rf.get("/admin/")
        req.user = attacker
        readonly = admin.get_readonly_fields(req, attacker)
        assert "is_superuser" in readonly
        assert "is_staff" in readonly

        su = django_user_model.objects.create_superuser(username="su", password="x")
        req.user = su
        assert "is_superuser" not in admin.get_readonly_fields(req, su)


@pytest.mark.django_db
class TestRoleAssignmentEscalation:
    def test_cannot_assign_role_without_permission(self, client, django_user_model, perms):
        plain = django_user_model.objects.create_user(username="plain", password="x")
        UserRole.objects.create(user=plain, role=make_role("r", "system:user:view"))
        client.force_login(plain)

        resp = client.post(
            reverse("accounts:user_role_assign", args=[plain.pk]),
            {"roles": [str(make_role("boss", "system:dept:delete").pk)]},
        )
        assert resp.status_code == 403

    def test_cannot_grant_role_beyond_own_permissions(self, client, attacker):
        """🔴 权限不可放大。

        attacker 有 assign_role 权限，但自己没有 system:dept:delete。
        他不能把一个含该权限的角色授予任何人（包括自己）。
        """
        boss = make_role("boss", "system:dept:delete")
        client.force_login(attacker)

        client.post(
            reverse("accounts:user_role_assign", args=[attacker.pk]),
            {"roles": [str(boss.pk)]},
        )

        assert "system:dept:delete" not in get_user_perm_codes(fresh(attacker))

    def test_can_grant_role_within_own_permissions(self, attacker):
        subset = make_role("subset", "system:user:view")
        assert can_grant_role(attacker, subset) is True

    def test_superuser_can_grant_anything(self, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        assert can_grant_role(su, make_role("boss", "system:dept:delete")) is True

    def test_anonymous_cannot_grant(self, perms):
        from django.contrib.auth.models import AnonymousUser

        assert can_grant_role(AnonymousUser(), make_role("r", "system:user:view")) is False


@pytest.mark.django_db
class TestPermissionAssignmentEscalation:
    def test_cannot_grant_permission_beyond_own(self, client, attacker):
        """🔴 v0.18.0 探测时发现的真实漏洞。

        attacker 有 system:role:assign_perm，但自己没有 system:dept:delete。
        在 v0.17.0 时他可以把那个权限加到自己的角色上——这就是提权。
        """
        own_role = Role.objects.get(code="perm_admin")
        target = Permission.objects.get(code="system:dept:delete")
        client.force_login(attacker)

        client.post(
            reverse("rbac:role_perm_assign", args=[own_role.pk]),
            {"permissions": [str(target.pk)]},
        )

        assert "system:dept:delete" not in get_user_perm_codes(fresh(attacker))

    def test_preserves_existing_perms_the_granter_cannot_grant(self, attacker, perms):
        """⚠️ 不能因为当前操作者动了别的选项，就把他授不出的既有权限清掉。

        那些可能是别人（更高权限的管理员）配的。
        """
        role = make_role("mixed", "system:dept:delete", "system:user:view")
        existing = set(
            RolePermission.objects.filter(role=role).values_list("permission_id", flat=True)
        )
        keep_only = Permission.objects.get(code="system:user:view")

        kept, rejected = filter_grantable_permission_ids(
            attacker, [str(keep_only.pk)], existing_ids=existing
        )

        delete_perm = Permission.objects.get(code="system:dept:delete")
        assert keep_only.pk in kept
        assert delete_perm.pk in kept  # 既有的、attacker 授不出的，保留下来
        assert rejected == set()

    def test_superuser_bypasses(self, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        target = Permission.objects.get(code="system:dept:delete")
        kept, rejected = filter_grantable_permission_ids(su, [str(target.pk)])
        assert kept == {str(target.pk)}
        assert rejected == set()
