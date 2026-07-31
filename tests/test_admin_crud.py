"""管理界面的 CRUD 路径。

覆盖率报告显示 views.py 只有 6 成——那些是管理员天天用的页面，
不该只靠「跑一遍演示」来验证。
"""

import pytest
from django.urls import reverse

from apps.accounts.models import Department
from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role, RoleDepartment, RolePermission, UserRole
from apps.common.demo import DEMO_PASSWORD, build_demo_world


@pytest.fixture
def world(db):
    return build_demo_world()


@pytest.fixture
def su(client, world):
    client.force_login(world["superadmin"])
    return client


# --------------------------------------------------------------------------- #
# 部门
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDepartmentCrud:
    def test_create(self, su, world):
        resp = su.post(
            reverse("accounts:department_create"),
            {"code": "NEW", "name": "新部门", "parent": world["cs"].pk, "order_num": 5,
             "is_active": "on"},
        )
        assert resp.status_code == 302
        dept = Department.objects.get(code="NEW")
        assert dept.path == f"{world['cs'].path}{dept.pk}/"
        assert dept.depth == 2

    def test_update_moves_subtree(self, su, world):
        su.post(
            reverse("accounts:department_update", args=[world["cs1"].pk]),
            {"code": "CS1", "name": "客服一组", "parent": world["tech"].pk,
             "order_num": 10, "is_active": "on"},
        )
        world["cs1"].refresh_from_db()
        assert world["cs1"].parent == world["tech"]

    def test_delete_protected_shows_message(self, su, world):
        """有子部门/在职用户时删除失败，且给出人话提示（FR-1.2）。"""
        resp = su.post(
            reverse("accounts:department_delete", args=[world["cs"].pk]), follow=True
        )
        assert Department.objects.filter(pk=world["cs"].pk).exists()
        assert "无法删除" in resp.content.decode()

    def test_delete_leaf_succeeds(self, su, world):
        leaf = Department.objects.create(code="TMP", name="临时组", parent=world["cs"])
        su.post(reverse("accounts:department_delete", args=[leaf.pk]))
        assert not Department.objects.filter(pk=leaf.pk).exists()

    def test_form_rejects_cycle(self, su, world):
        """把上级设成自己的后代——表单下拉里根本选不到，直接 POST 也要挡住。"""
        resp = su.post(
            reverse("accounts:department_update", args=[world["cs"].pk]),
            {"code": "CS", "name": "客服部", "parent": world["cs1"].pk,
             "order_num": 10, "is_active": "on"},
        )
        assert resp.status_code == 200  # 回到表单，没有重定向
        world["cs"].refresh_from_db()
        assert world["cs"].parent == world["hq"]


# --------------------------------------------------------------------------- #
# 用户
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestUserCrud:
    def test_create(self, su, world, django_user_model):
        su.post(
            reverse("accounts:user_create"),
            {"username": "newbie", "real_name": "新人", "phone": "13800000000",
             "email": "newbie@example.com", "department": world["cs1"].pk, "is_active": "on",
             "password1": "Str0ngPass!2026", "password2": "Str0ngPass!2026"},
        )
        u = django_user_model.objects.get(username="newbie")
        assert u.department == world["cs1"]
        assert u.check_password("Str0ngPass!2026")

    def test_list_filters(self, su, world):
        resp = su.get(reverse("accounts:user_list"), {"kw": "cs_staff"})
        assert resp.context["page"].paginator.count == 1

        resp = su.get(reverse("accounts:user_list"), {"dept": world["cs"].pk})
        # 客服部子树下的用户：cs_manager / cs_staff / no_role
        assert resp.context["page"].paginator.count == 3

    def test_cannot_delete_superuser_from_ui(self, su, world):
        resp = su.post(
            reverse("accounts:user_delete", args=[world["superadmin"].pk]), follow=True
        )
        assert type(world["superadmin"]).objects.filter(
            pk=world["superadmin"].pk
        ).exists()
        assert "不可从界面删除" in resp.content.decode()

    def test_role_assignment_roundtrip(self, su, world):
        target = world["no_role"]
        role = world["roles"]["specialist"]

        su.post(reverse("accounts:user_role_assign", args=[target.pk]),
                {"roles": [str(role.pk)]})

        assert UserRole.objects.filter(user=target, role=role).exists()
        assert UserRole.objects.get(user=target, role=role).granted_by == world["superadmin"]


# --------------------------------------------------------------------------- #
# 角色
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestRoleCrud:
    def test_create(self, su):
        su.post(
            reverse("rbac:role_create"),
            {"code": "newrole", "name": "新角色", "description": "",
             "data_scope": DataScope.DEPT_ONLY, "order_num": 0, "is_active": "on"},
        )
        role = Role.objects.get(code="newrole")
        assert role.data_scope == DataScope.DEPT_ONLY

    def test_create_defaults_to_narrowest_scope(self, su):
        """不填 data_scope 时表单会用模型默认值 SELF_ONLY。"""
        assert Role._meta.get_field("data_scope").default == DataScope.SELF_ONLY

    def test_update_sets_inheritance(self, su, world):
        role = world["roles"]["empty"]
        su.post(
            reverse("rbac:role_update", args=[role.pk]),
            {"code": role.code, "name": role.name, "description": "",
             "inherits_from": world["roles"]["specialist"].pk,
             "data_scope": role.data_scope, "order_num": 0, "is_active": "on"},
        )
        role.refresh_from_db()
        assert role.inherits_from == world["roles"]["specialist"]

    def test_delete(self, su, world):
        role = world["roles"]["empty"]
        su.post(reverse("rbac:role_delete", args=[role.pk]))
        assert not Role.objects.filter(pk=role.pk).exists()

    def test_perm_assign_page_marks_inherited(self, su, world):
        resp = su.get(
            reverse("rbac:role_perm_assign", args=[world["roles"]["manager"].pk])
        )
        rows = resp.context["rows"]
        inherited = [r for r in rows if r["inherited"]]
        assert inherited, "客服主管继承自客服专员，应有只读的继承项"
        assert resp.context["has_inherited"] is True

    def test_effective_perms_page(self, su, world):
        resp = su.get(
            reverse("rbac:role_effective_perms", args=[world["roles"]["manager"].pk])
        )
        html = resp.content.decode()
        assert "继承自 客服专员" in html
        assert "直接授予" in html

    def test_data_scope_page_roundtrip(self, su, world):
        role = world["roles"]["empty"]
        su.post(
            reverse("rbac:role_data_scope", args=[role.pk]),
            {"data_scope": DataScope.CUSTOM, "departments": [str(world["cs"].pk)]},
        )
        role.refresh_from_db()
        assert role.data_scope == DataScope.CUSTOM
        assert RoleDepartment.objects.filter(role=role, department=world["cs"]).exists()

    def test_data_scope_page_drops_departments_when_not_custom(self, su, world):
        role = world["roles"]["empty"]
        su.post(
            reverse("rbac:role_data_scope", args=[role.pk]),
            {"data_scope": DataScope.SELF_ONLY, "departments": [str(world["cs"].pk)]},
        )
        assert RoleDepartment.objects.filter(role=role).count() == 0


# --------------------------------------------------------------------------- #
# 工单
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestTicketCrud:
    def test_create_update_assign_delete(self, client, world):
        from apps.tickets.models import Ticket

        client.force_login(world["cs_manager"])

        client.post(reverse("tickets:create"),
                    {"title": "主管的单", "content": "内容", "priority": 3, "status": "open"})
        ticket = Ticket.objects.get(title="主管的单")
        assert ticket.department == world["cs"]

        client.post(reverse("tickets:update", args=[ticket.pk]),
                    {"title": "改过的", "content": "x", "priority": 1, "status": "processing"})
        ticket.refresh_from_db()
        assert ticket.title == "改过的"

        client.post(reverse("tickets:assign", args=[ticket.pk]),
                    {"assignee": world["cs_staff"].pk})
        ticket.refresh_from_db()
        assert ticket.assignee == world["cs_staff"]

        client.post(reverse("tickets:delete", args=[ticket.pk]))
        assert not Ticket.objects.filter(pk=ticket.pk).exists()

    def test_user_without_department_cannot_create(self, client, world, django_user_model):
        orphan = django_user_model.objects.create_user(
            username="orphan", password=DEMO_PASSWORD, department=None
        )
        UserRole.objects.create(user=orphan, role=world["roles"]["specialist"])
        client.force_login(orphan)

        resp = client.post(reverse("tickets:create"),
                           {"title": "无部门", "priority": 2, "status": "open"}, follow=True)
        assert "尚未归属任何部门" in resp.content.decode()

    def test_list_filters(self, client, world):
        client.force_login(world["cs_manager"])
        resp = client.get(reverse("tickets:list"), {"kw": "客服二组"})
        assert resp.context["page"].paginator.count == 15

        resp = client.get(reverse("tickets:list"), {"status": "open"})
        assert resp.context["page"].paginator.count == 50


# --------------------------------------------------------------------------- #
# 权限点页面
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestPermissionList:
    def test_shows_tree(self, su):
        resp = su.get(reverse("rbac:permission_list"))
        html = resp.content.decode()
        assert "system:dept:view" in html
        assert "sync_permissions" in html  # 页面上说明了权限点的来源

    def test_deprecated_marked(self, su):
        Permission.objects.filter(code="system:dept:delete").update(is_deprecated=True)
        html = su.get(reverse("rbac:permission_list")).content.decode()
        assert "已废弃" in html


@pytest.mark.django_db
class TestAuditList:
    def test_filters(self, su, world):
        from apps.audit.constants import AuditAction
        from apps.audit.services import log

        log(AuditAction.LOGIN, actor=world["cs_staff"])
        log(AuditAction.LOGOUT, actor=world["cs_staff"])

        resp = su.get(reverse("audit:log_list"), {"action": AuditAction.LOGIN})
        assert resp.context["page"].paginator.count == 1

        resp = su.get(reverse("audit:log_list"), {"kw": "cs_staff"})
        assert resp.context["page"].paginator.count == 2
