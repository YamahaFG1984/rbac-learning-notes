import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.cache import bump_version, get_version
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import expand_roles, get_user_perm_codes, save_role_permissions


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def make_role(code, *perm_codes, inherits_from=None):
    role = Role.objects.create(code=code, name=code, inherits_from=inherits_from)
    for pc in perm_codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=pc))
    return role


@pytest.fixture
def staff(django_user_model, perms):
    user = django_user_model.objects.create_user(username="staff", password="x")
    UserRole.objects.create(user=user, role=make_role("r", "system:dept:view"))
    return user


def fresh(user):
    """拿一个没有 L1 请求级缓存的 user 对象。"""
    return type(user).objects.get(pk=user.pk)


@pytest.mark.django_db
class TestRequestLevelCache:
    def test_resolves_once_per_user_object(self, staff, django_assert_num_queries):
        user = fresh(staff)
        # 3 = 全量角色映射 + 用户的直接角色 + 权限码
        with django_assert_num_queries(3):
            get_user_perm_codes(user)
        # 同一个 user 对象上再判断 50 次：0 查询
        with django_assert_num_queries(0):
            for _ in range(50):
                get_user_perm_codes(user)

    def test_cache_lives_on_user_not_request(self, staff):
        """挂在 user 上而不是 request 上——services 不认识 request（ADR-013），
        挂 user 上 Web 层和 API 层都能用。"""
        user = fresh(staff)
        get_user_perm_codes(user)
        assert hasattr(user, "_rbac_perm_cache")


@pytest.mark.django_db
class TestProcessCache:
    def test_second_user_object_hits_l2(self, staff, django_assert_num_queries):
        get_user_perm_codes(fresh(staff))  # 预热 L2
        another = fresh(staff)  # 新对象，没有 L1 缓存
        with django_assert_num_queries(0):
            get_user_perm_codes(another)

    def test_expand_roles_is_query_free(self, perms, django_user_model):
        c = make_role("c", "system:dept:view")
        b = make_role("b", inherits_from=c)
        a = make_role("a", inherits_from=b)
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=a)

        get_user_perm_codes(fresh(user))  # 预热角色映射

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            expanded = expand_roles([a])
        assert len(ctx) == 0, "角色映射已缓存，展开继承链不该再查库"
        assert {r.pk for r in expanded} == {a.pk, b.pk, c.pk}


@pytest.mark.django_db
class TestInvalidation:
    def test_version_bumps_on_role_permission_change(self, staff):
        before = get_version()
        RolePermission.objects.create(
            role=Role.objects.get(code="r"),
            permission=Permission.objects.get(code="system:dept:create"),
        )
        assert get_version() > before

    def test_revoking_role_takes_effect_immediately(self, staff):
        """🔴 撤权后**立即**生效，不等 TTL 过期（FR-4.5）。"""
        assert "system:dept:view" in get_user_perm_codes(fresh(staff))

        UserRole.objects.filter(user=staff).delete()

        assert get_user_perm_codes(fresh(staff)) == frozenset()

    def test_granting_perm_takes_effect_immediately(self, staff):
        """US-3：管理员配完，用户刷新即见，无需重新登录。"""
        assert "system:dept:create" not in get_user_perm_codes(fresh(staff))

        role = Role.objects.get(code="r")
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code="system:dept:create")
        )

        assert "system:dept:create" in get_user_perm_codes(fresh(staff))

    def test_ancestor_role_change_propagates(self, perms, django_user_model):
        """🔴 逐 key 删除方案最容易漏掉的情形：改的是祖先角色。"""
        ancestor = make_role("ancestor")
        child = make_role("child", inherits_from=ancestor)
        user = django_user_model.objects.create_user(username="u", password="x")
        UserRole.objects.create(user=user, role=child)

        assert get_user_perm_codes(fresh(user)) == frozenset()

        RolePermission.objects.create(
            role=ancestor, permission=Permission.objects.get(code="system:role:view")
        )

        assert "system:role:view" in get_user_perm_codes(fresh(user))

    def test_bulk_create_path_also_invalidates(self, staff):
        """⚠️ bulk_create **不触发** post_save 信号。

        save_role_permissions 用的就是 bulk_create——光挂 signals.py 是不够的，
        必须在函数里显式 bump 一次。
        """
        role = Role.objects.get(code="r")
        target = Permission.objects.get(code="system:role:view")

        assert "system:role:view" not in get_user_perm_codes(fresh(staff))

        save_role_permissions(role, [target.pk])

        assert "system:role:view" in get_user_perm_codes(fresh(staff))

    def test_custom_dept_change_invalidates(self, perms, django_user_model):
        from apps.accounts.models import Department
        from apps.rbac.constants import DataScope
        from apps.rbac.services import get_role_custom_dept_ids, save_role_departments

        dept = Department.objects.create(code="D", name="部门")
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.CUSTOM)

        assert get_role_custom_dept_ids(role) == set()

        save_role_departments(role, [dept.pk])

        assert get_role_custom_dept_ids(role) == {dept.pk}

    def test_sync_permissions_invalidates(self, staff):
        before = get_version()
        call_command("sync_permissions", verbosity=0)
        assert get_version() > before

    def test_bump_is_idempotent_when_key_missing(self):
        cache.clear()
        bump_version()  # key 不存在时不能抛异常
        assert get_version() >= 1


@pytest.mark.django_db
class TestSuperuserBypassesCache:
    def test_no_queries_and_no_cache_entry(
        self, perms, django_user_model, django_assert_num_queries
    ):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        with django_assert_num_queries(0):
            get_user_perm_codes(su)


@pytest.mark.django_db
class TestEndToEndQueryReduction:
    def test_permission_resolution_no_longer_repeated(self, client, staff, perms):
        """v0.13.0 实测到「一次请求里权限解析重复 3 次」，现在应降到 0 次。"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client.force_login(staff)
        client.get(reverse("accounts:department_list"))  # 预热 L2

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(reverse("accounts:department_list"))

        assert resp.status_code == 200

        # 权限解析 = 查角色 + 查权限码
        resolution = [
            q
            for q in ctx.captured_queries
            if 'FROM "rbac_role"' in q["sql"]
            or ('FROM "rbac_permission"' in q["sql"] and "rolepermission" in q["sql"].lower())
        ]
        assert len(resolution) == 0, (
            f"权限解析应全部命中缓存（v0.13.0 时是 3 次），实测 {len(resolution)} 次：\n"
            + "\n".join(q["sql"][:90] for q in resolution)
        )

    def test_menu_node_query_is_deliberately_not_cached(self, client, staff, perms):
        """菜单**节点**的查询没有缓存，这是刻意的。

        get_user_menu_tree 依赖的权限码已经命中缓存了，但取菜单节点那一次
        SELECT 仍然会发生。要不要连它一起缓存，是 v0.11.0 延伸思考 1 留的
        开放问题：

          · 缓存 key 该带用户 ID，还是带「权限码集合的哈希」让权限相同的
            用户共享？
          · 后者在什么规模下才值得？

        本项目留白不实现——它是**一次**固定查询，与菜单层级和用户数无关，
        和「重复解析 3 次权限」不是一个量级的问题。
        先把真问题解决掉，别顺手做没量化过收益的优化。
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client.force_login(staff)
        client.get(reverse("accounts:department_list"))  # 预热

        with CaptureQueriesContext(connection) as ctx:
            client.get(reverse("accounts:department_list"))

        menu_queries = [
            q for q in ctx.captured_queries if "perm_type" in q["sql"]
        ]
        assert len(menu_queries) == 1
