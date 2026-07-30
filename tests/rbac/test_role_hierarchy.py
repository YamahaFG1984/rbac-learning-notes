"""角色继承（RBAC0 -> RBAC1）。"""

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import (
    expand_roles,
    get_role_effective_codes,
    get_role_perm_sources,
    get_user_perm_codes,
)


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def make_role(code, *perm_codes, inherits_from=None, is_active=True):
    role = Role.objects.create(
        code=code, name=code, inherits_from=inherits_from, is_active=is_active
    )
    for pc in perm_codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=pc))
    return role


@pytest.mark.django_db
class TestInheritance:
    def test_child_gets_parent_perms(self, perms, django_user_model):
        specialist = make_role("specialist", "system:dept:view")
        manager = make_role("manager", "system:dept:create", inherits_from=specialist)

        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=manager)

        assert get_user_perm_codes(user) == {"system:dept:view", "system:dept:create"}

    def test_three_levels(self, perms, django_user_model):
        c = make_role("c", "system:dept:view")
        b = make_role("b", "system:dept:create", inherits_from=c)
        a = make_role("a", "system:dept:update", inherits_from=b)

        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=a)

        assert get_user_perm_codes(user) == {
            "system:dept:view",
            "system:dept:create",
            "system:dept:update",
        }

    def test_adding_perm_to_ancestor_propagates_immediately(
        self, perms, django_user_model
    ):
        """US-4：给专员加权限，主管自动获得，不需要任何额外操作。"""
        c = make_role("c")
        b = make_role("b", inherits_from=c)
        a = make_role("a", inherits_from=b)
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=a)

        assert get_user_perm_codes(user) == frozenset()

        RolePermission.objects.create(
            role=c, permission=Permission.objects.get(code="system:role:view")
        )
        assert "system:role:view" in get_user_perm_codes(user)

    def test_inactive_ancestor_perms_dropped(self, perms, django_user_model):
        parent = make_role("parent", "system:dept:view", is_active=False)
        child = make_role("child", "system:dept:create", inherits_from=parent)
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=child)

        assert get_user_perm_codes(user) == {"system:dept:create"}

    def test_shared_ancestor_expanded_once(self, perms):
        base = make_role("base", "system:dept:view")
        a = make_role("a", inherits_from=base)
        b = make_role("b", inherits_from=base)

        expanded = expand_roles([a, b])
        assert expanded == {a, b, base}
        assert len(expanded) == 3  # base 只出现一次


@pytest.mark.django_db
class TestCycleAndDepth:
    def test_self_inheritance_rejected(self, perms):
        role = make_role("r")
        role.inherits_from = role
        with pytest.raises(ValidationError, match="不能继承自己"):
            role.full_clean()

    def test_cycle_rejected(self, perms):
        a = make_role("a")
        b = make_role("b", inherits_from=a)
        c = make_role("c", inherits_from=b)

        a.inherits_from = c
        with pytest.raises(ValidationError, match="继承环"):
            a.full_clean()

    def test_cycle_rejected_on_save_too(self, perms):
        """ModelForm.is_valid() 会调 full_clean()，但 Model.save() 不会。
        我们在 save() 里补了一道，这样 shell / 管理命令也挡得住。"""
        a = make_role("a")
        b = make_role("b", inherits_from=a)
        a.inherits_from = b
        with pytest.raises(ValidationError):
            a.save()

    def test_depth_limit_enforced(self, perms):
        previous = None
        for i in range(settings.RBAC_MAX_ROLE_DEPTH):
            previous = make_role(f"lvl{i}", inherits_from=previous)

        too_deep = Role(code="toodeep", name="toodeep", inherits_from=previous)
        with pytest.raises(ValidationError, match="深度"):
            too_deep.full_clean()

    def test_expand_survives_corrupted_cycle_in_db(self, perms):
        """纵深防御：clean() 防止环被存进去，expand_roles 防止已存在的环导致死循环。

        用 update() 绕过 save()/clean() 直接在库里造一个环。
        """
        a = make_role("a", "system:dept:view")
        b = make_role("b", "system:dept:create", inherits_from=a)
        Role.objects.filter(pk=a.pk).update(inherits_from_id=b.pk)

        a.refresh_from_db()
        b.refresh_from_db()

        expanded = expand_roles([b])  # 不能死循环
        assert {r.pk for r in expanded} == {a.pk, b.pk}


@pytest.mark.django_db
class TestPermSources:
    def test_traces_each_code_to_its_role(self, perms):
        base = make_role("base", "system:dept:view")
        mid = make_role("mid", "system:dept:create", inherits_from=base)
        top = make_role("top", "system:dept:update", inherits_from=mid)

        sources = get_role_perm_sources(top)

        assert sources["system:dept:view"] == base
        assert sources["system:dept:create"] == mid
        assert sources["system:dept:update"] == top

    def test_direct_grant_overrides_inherited_source(self, perms):
        """同一个权限码既继承又直接授予时，显示最近的来源。"""
        base = make_role("base", "system:dept:view")
        top = make_role("top", "system:dept:view", inherits_from=base)

        assert get_role_perm_sources(top)["system:dept:view"] == top

    def test_effective_codes(self, perms):
        base = make_role("base", "system:dept:view")
        top = make_role("top", "system:dept:create", inherits_from=base)
        assert get_role_effective_codes(top) == {"system:dept:view", "system:dept:create"}


@pytest.mark.django_db
class TestForm:
    def test_parent_choices_exclude_self_and_descendants(self, perms):
        from apps.rbac.forms import RoleForm

        a = make_role("a")
        b = make_role("b", inherits_from=a)
        c = make_role("c", inherits_from=b)
        other = make_role("other")

        choices = set(RoleForm(instance=a).fields["inherits_from"].queryset)

        assert other in choices
        assert a not in choices  # 自己
        assert b not in choices  # 后代
        assert c not in choices  # 后代的后代


@pytest.mark.django_db
class TestViews:
    @pytest.fixture
    def su_client(self, client, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        client.force_login(su)
        return client

    def test_effective_perms_page(self, su_client, perms):
        base = make_role("base", "system:dept:view")
        top = make_role("top", "system:dept:create", inherits_from=base)

        resp = su_client.get(reverse("rbac:role_effective_perms", args=[top.pk]))

        assert resp.status_code == 200
        html = resp.content.decode()
        assert "system:dept:view" in html
        assert "继承自 base" in html
        assert "直接授予" in html

    def test_inherited_perm_shown_readonly(self, su_client, perms):
        base = make_role("base", "system:dept:view")
        top = make_role("top", inherits_from=base)

        html = su_client.get(
            reverse("rbac:role_perm_assign", args=[top.pk])
        ).content.decode()

        assert "disabled" in html
        assert "继承" in html

    def test_direct_grant_stays_editable_even_if_also_inherited(self, su_client, perms):
        """⚠️ disabled 的 checkbox 不会被提交。

        如果一个权限既是直接授予又是继承来的，禁用它会导致保存时
        把直接授权静默删掉——所以只对「纯继承」的项禁用。
        """
        base = make_role("base", "system:dept:view")
        top = make_role("top", "system:dept:view", inherits_from=base)

        perm = Permission.objects.get(code="system:dept:view")
        resp = su_client.get(reverse("rbac:role_perm_assign", args=[top.pk]))
        row = next(r for r in resp.context["rows"] if r["obj"].pk == perm.pk)

        assert row["checked"] is True
        assert row["inherited"] is False  # 不禁用，因为它是直接授予的
