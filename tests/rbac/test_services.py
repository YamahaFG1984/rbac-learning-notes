"""权限内核单元测试。

⚠️ 本 tag 的验收重心在这里，不在界面——内核对不对，只有测试能证明。
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import (
    ALL_PERMS,
    get_user_perm_codes,
    save_user_roles,
    user_has_all_perms,
    user_has_any_perm,
    user_has_perm,
)


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def make_role(code, *perm_codes, is_active=True):
    role = Role.objects.create(code=code, name=code, is_active=is_active)
    for pc in perm_codes:
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code=pc)
        )
    return role


@pytest.mark.django_db
class TestDenyByDefault:
    """这些分支在正常使用中永远不会被触发——只有测试能保证它们是对的。"""

    def test_anonymous_returns_empty(self, perms):
        assert get_user_perm_codes(AnonymousUser()) == frozenset()

    def test_none_user_returns_empty(self, perms):
        assert get_user_perm_codes(None) == frozenset()

    def test_inactive_user_returns_empty(self, perms, django_user_model):
        """用户被禁用后 session 还在，request.user 仍是那个对象。
        不检查 is_active 的话，禁用账号在 session 过期前还能操作。"""
        user = django_user_model.objects.create_user(
            username="u", password="x", is_active=False
        )
        make_role("r", "system:dept:view")
        UserRole.objects.create(user=user, role=Role.objects.get(code="r"))
        assert get_user_perm_codes(user) == frozenset()

    def test_user_without_role_returns_empty(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        assert get_user_perm_codes(user) == frozenset()
        assert user_has_perm(user, "system:dept:view") is False


@pytest.mark.django_db
class TestSuperuser:
    def test_contains_anything(self, perms, django_user_model):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        codes = get_user_perm_codes(su)
        assert codes is ALL_PERMS
        assert "any:thing:at_all" in codes
        assert user_has_perm(su, "not:in:database") is True

    def test_short_circuits_without_query(self, perms, django_user_model, django_assert_num_queries):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        with django_assert_num_queries(0):
            user_has_perm(su, "system:dept:view")

    def test_is_truthy_but_empty_when_iterated(self, perms, django_user_model):
        """哨兵对象只在 `in` 这一个语义上成立——用它的地方越多越容易踩空。"""
        su = django_user_model.objects.create_superuser(username="su", password="x")
        codes = get_user_perm_codes(su)
        assert bool(codes) is True
        assert list(codes) == []
        assert len(codes) == 0


@pytest.mark.django_db
class TestResolution:
    def test_single_role(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        role = make_role("r", "system:dept:view", "system:dept:create")
        UserRole.objects.create(user=user, role=role)
        assert get_user_perm_codes(user) == {"system:dept:view", "system:dept:create"}

    def test_multi_roles_take_union_not_intersection(self, perms, django_user_model):
        """FR-4.1：多角色权限取并集。现实中一个人身兼两职，
        自然是两份职责的权限都有，而不是只有交集那部分。"""
        user = django_user_model.objects.create_user(username="u", password="x")
        a = make_role("a", "system:dept:view", "system:dept:create")
        b = make_role("b", "system:dept:view", "system:role:view")
        UserRole.objects.create(user=user, role=a)
        UserRole.objects.create(user=user, role=b)

        codes = get_user_perm_codes(user)
        assert codes == {"system:dept:view", "system:dept:create", "system:role:view"}
        # 交集只有 1 个，并集是 3 个——断言我们拿的是后者
        assert len(codes) == 3

    def test_catalog_none_code_excluded(self, perms, django_user_model):
        """catalog 没有权限码。漏了 exclude 的话 None 会混进集合里。"""
        user = django_user_model.objects.create_user(username="u", password="x")
        role = Role.objects.create(code="r", name="r")
        catalog = Permission.objects.filter(code__isnull=True).first()
        assert catalog is not None
        RolePermission.objects.create(role=role, permission=catalog)
        UserRole.objects.create(user=user, role=role)

        codes = get_user_perm_codes(user)
        assert None not in codes
        assert codes == frozenset()

    def test_deprecated_permission_excluded(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        role = make_role("r", "system:dept:view")
        UserRole.objects.create(user=user, role=role)
        assert "system:dept:view" in get_user_perm_codes(user)

        Permission.objects.filter(code="system:dept:view").update(is_deprecated=True)
        assert "system:dept:view" not in get_user_perm_codes(user)

    def test_inactive_role_excluded(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        role = make_role("r", "system:dept:view", is_active=False)
        UserRole.objects.create(user=user, role=role)
        assert get_user_perm_codes(user) == frozenset()

    def test_returns_frozenset(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        assert isinstance(get_user_perm_codes(user), frozenset)

    def test_query_count(self, perms, django_user_model, django_assert_num_queries):
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=make_role("r", "system:dept:view"))
        # 2 = 角色 ID SELECT + 权限码 SELECT。本 tag 无缓存，v0.16.0 会降到 0/1。
        with django_assert_num_queries(2):
            get_user_perm_codes(user)


@pytest.mark.django_db
class TestHelpers:
    def test_any_and_all(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(
            user=user, role=make_role("r", "system:dept:view", "system:dept:create")
        )
        assert user_has_any_perm(user, ["nope:no:view", "system:dept:view"]) is True
        assert user_has_any_perm(user, ["nope:no:view"]) is False
        assert user_has_all_perms(user, ["system:dept:view", "system:dept:create"]) is True
        assert user_has_all_perms(user, ["system:dept:view", "system:role:view"]) is False


@pytest.mark.django_db
class TestSaveUserRoles:
    def test_roundtrip_and_overwrite(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        a, b, c = make_role("a"), make_role("b"), make_role("c")

        save_user_roles(user, [a.pk, b.pk])
        assert set(UserRole.objects.filter(user=user).values_list("role_id", flat=True)) == {
            a.pk,
            b.pk,
        }

        save_user_roles(user, [c.pk])
        assert set(UserRole.objects.filter(user=user).values_list("role_id", flat=True)) == {
            c.pk
        }

    def test_rejects_unknown_and_inactive_roles(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        good = make_role("good")
        dead = make_role("dead", is_active=False)

        save_user_roles(user, [good.pk, dead.pk, 999999])

        assert set(UserRole.objects.filter(user=user).values_list("role_id", flat=True)) == {
            good.pk
        }

    def test_records_granted_by(self, perms, django_user_model):
        user = django_user_model.objects.create_user(username="u", password="x")
        admin = django_user_model.objects.create_user(username="admin", password="x")
        role = make_role("r")

        save_user_roles(user, [role.pk], granted_by=admin)

        ur = UserRole.objects.get(user=user, role=role)
        assert ur.granted_by == admin
        assert ur.granted_at is not None


@pytest.mark.django_db
class TestKernelPurity:
    FORBIDDEN_PREFIXES = ("django.http", "django.shortcuts", "django.views", "rest_framework")

    def test_services_imports_nothing_from_presentation_layer(self):
        """ADR-013：内核不认识 HTTP。这条约束的收益在 v1.2.0 兑现。

        用 AST 解析真实的 import 语句，不是 grep 源码文本
        ——docstring 里提到「禁止 import django.http」时，grep 会误判。
        """
        import ast
        import inspect

        from apps.rbac import services

        tree = ast.parse(inspect.getsource(services))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        offenders = [
            m for m in imported if m.startswith(self.FORBIDDEN_PREFIXES)
        ]
        assert not offenders, (
            f"权限内核不得依赖表现层：{offenders}。"
            f"「不通过之后做什么」是 Web / API 各自的事（ADR-013）。"
        )

    def test_kernel_functions_do_not_take_request(self):
        import inspect

        from apps.rbac import services

        for name, fn in inspect.getmembers(services, inspect.isfunction):
            if fn.__module__ != services.__name__:
                continue
            assert "request" not in inspect.signature(fn).parameters, (
                f"{name}() 不该接收 request——那是表现层的东西"
            )
