import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import get_user_menu_tree


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def grant(user, *codes):
    role = Role.objects.create(code=f"r{user.pk}", name="r")
    for c in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=c))
    UserRole.objects.create(user=user, role=role)


@pytest.fixture
def staff(django_user_model, perms):
    return django_user_model.objects.create_user(username="staff", password="x")


def names(tree):
    return [n["name"] for n in tree]


@pytest.mark.django_db
class TestMenuTree:
    def test_no_role_gets_empty_tree(self, staff):
        assert get_user_menu_tree(staff) == []

    def test_only_permitted_catalog_appears(self, staff):
        grant(staff, "system:role:view")
        tree = get_user_menu_tree(staff)
        assert names(tree) == ["权限管理"]
        assert names(tree[0]["children"]) == ["角色管理"]

    def test_empty_catalog_is_dropped(self, staff):
        """⚠️ 一个点开是空的目录，用户会以为系统坏了。

        目录没有权限码，判断不了自己——所以算法必须自底向上：
        先标记有权限的 menu，再向上保留祖先。空目录自然不会被保留。
        """
        grant(staff, "system:dept:view")
        tree = get_user_menu_tree(staff)
        assert names(tree) == ["组织管理"]  # 「权限管理」「工单管理」整个不出现
        assert names(tree[0]["children"]) == ["部门管理"]  # 「用户管理」也不出现

    def test_superuser_sees_everything(self, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        tree = get_user_menu_tree(su)
        # 目录按 order_num 排：工单管理(5) < 组织管理(10) < 权限管理(20)
        assert names(tree) == ["工单管理", "组织管理", "权限管理"]
        assert names(tree[1]["children"]) == ["部门管理", "用户管理"]
        assert names(tree[2]["children"]) == ["角色管理", "权限点"]

    def test_buttons_never_appear(self, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        tree = get_user_menu_tree(su)
        for catalog in tree:
            for child in catalog["children"]:
                assert child["perm_type"] == "menu"
                assert child["children"] == []  # button 不进菜单

    def test_invisible_menu_excluded(self, staff):
        grant(staff, "system:dept:view", "system:user:view")
        Permission.objects.filter(code="system:user:view").update(is_visible=False)
        tree = get_user_menu_tree(staff)
        assert names(tree[0]["children"]) == ["部门管理"]

    def test_deprecated_menu_excluded(self, staff):
        grant(staff, "system:dept:view", "system:user:view")
        Permission.objects.filter(code="system:user:view").update(is_deprecated=True)
        tree = get_user_menu_tree(staff)
        assert names(tree[0]["children"]) == ["部门管理"]

    def test_children_ordered_by_order_num(self, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        tree = get_user_menu_tree(su)
        org = next(n for n in tree if n["name"] == "组织管理")
        # 部门管理 order=10，用户管理 order=20
        assert names(org["children"]) == ["部门管理", "用户管理"]

    def test_url_is_reversed(self, staff):
        grant(staff, "system:dept:view")
        tree = get_user_menu_tree(staff)
        assert tree[0]["children"][0]["url"] == reverse("accounts:department_list")

    def test_broken_url_name_does_not_crash(self, staff):
        """一个写错的 url_name 不能让整个侧边栏崩溃——那会导致所有页面都打不开。"""
        grant(staff, "system:dept:view")
        Permission.objects.filter(code="system:dept:view").update(
            url_name="accounts:no_such_view"
        )
        tree = get_user_menu_tree(staff)
        assert tree[0]["children"][0]["url"] is None  # 降级为不可点，不抛异常


@pytest.mark.django_db
class TestQueryCount:
    def test_single_query_regardless_of_depth(self, staff, django_assert_num_queries):
        """NFR-3：菜单树构建的查询次数与层级无关。"""
        grant(staff, "system:dept:view")

        # 3 = 权限解析 2（角色 ID + 权限码）+ 菜单节点全量 1
        with django_assert_num_queries(3):
            get_user_menu_tree(staff)

        # 加深一层：在「组织管理」下再插一层目录
        catalog = Permission.objects.get(name="组织管理")
        deeper = Permission.objects.create(
            name="更深的目录", perm_type="catalog", parent=catalog, order_num=99
        )
        Permission.objects.filter(code="system:user:view").update(parent=deeper)

        # 数字**不变**——递归查库的实现会随层级增长
        with django_assert_num_queries(3):
            get_user_menu_tree(staff)


@pytest.mark.django_db
class TestSidebarRendering:
    def test_sidebar_shows_only_permitted(self, client, staff):
        grant(staff, "system:dept:view")
        client.force_login(staff)
        html = client.get(reverse("accounts:department_list")).content.decode()
        assert "部门管理" in html
        assert "角色管理" not in html
        assert "权限管理" not in html

    def test_sidebar_hints_when_no_menu(self, client, staff, django_user_model):
        """无角色用户看到的不是空白，而是一句说明。"""
        grant(staff, "system:dept:view")
        client.force_login(staff)
        # 撤销权限后侧边栏为空
        UserRole.objects.filter(user=staff).delete()
        resp = client.get(reverse("accounts:department_list"))
        assert resp.status_code == 403  # 连页面都进不去了，符合预期
