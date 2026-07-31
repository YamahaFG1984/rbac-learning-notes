import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Department
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.tickets.models import Ticket
from apps.tickets.permissions import TicketPerm


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


@pytest.fixture
def depts(db):
    hq = Department.objects.create(code="HQ", name="总部")
    cs = Department.objects.create(code="CS", name="客服部", parent=hq)
    tech = Department.objects.create(code="TECH", name="技术部", parent=hq)
    return {"hq": hq, "cs": cs, "tech": tech}


def grant(user, *codes):
    role = Role.objects.create(code=f"r{user.pk}", name="r")
    for c in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=c))
    UserRole.objects.create(user=user, role=role)
    return role


@pytest.fixture
def staff(django_user_model, perms, depts):
    return django_user_model.objects.create_user(
        username="staff", password="x", department=depts["cs"]
    )


@pytest.fixture
def tickets(staff, depts, django_user_model):
    other = django_user_model.objects.create_user(
        username="tech_guy", password="x", department=depts["tech"]
    )
    made = []
    for i in range(5):
        made.append(
            Ticket.objects.create(
                title=f"客服工单{i}", creator=staff, department=depts["cs"]
            )
        )
    for i in range(3):
        made.append(
            Ticket.objects.create(
                title=f"技术工单{i}", creator=other, department=depts["tech"]
            )
        )
    return made


@pytest.mark.django_db
class TestFunctionalPermissions:
    @staticmethod
    def _widen(role):
        from apps.rbac.constants import DataScope

        role.data_scope = DataScope.ALL
        role.save()
        return role

    def test_list_requires_view_perm(self, client, staff):
        client.force_login(staff)
        assert client.get(reverse("tickets:list")).status_code == 403

        grant(staff, TicketPerm.VIEW)
        assert client.get(reverse("tickets:list")).status_code == 200

    def test_delete_button_hidden_and_post_rejected(self, client, staff, tickets):
        self._widen(grant(staff, TicketPerm.VIEW))
        client.force_login(staff)

        html = client.get(reverse("tickets:list")).content.decode()
        assert "删除" not in html

        resp = client.post(reverse("tickets:delete", args=[tickets[0].pk]))
        assert resp.status_code == 403
        assert Ticket.objects.filter(pk=tickets[0].pk).exists()

    def test_assign_has_its_own_perm(self, client, staff, tickets):
        """派单不是普通编辑——独立按钮就该有独立权限点。"""
        grant(staff, TicketPerm.VIEW, TicketPerm.UPDATE)
        client.force_login(staff)
        assert client.get(reverse("tickets:assign", args=[tickets[0].pk])).status_code == 403


@pytest.mark.django_db
class TestDepartmentSnapshot:
    def test_department_is_snapshotted_on_create(self, client, staff, depts):
        grant(staff, TicketPerm.VIEW, TicketPerm.CREATE)
        client.force_login(staff)

        client.post(reverse("tickets:create"), {"title": "新单", "priority": 2, "status": "open"})

        ticket = Ticket.objects.get(title="新单")
        assert ticket.creator == staff
        assert ticket.department == depts["cs"]

    def test_snapshot_survives_creator_transfer(self, staff, depts):
        """⚠️ 快照 vs 引用。

        如果查询时用 creator.department，创建人转岗后他以前创建的所有工单
        会跟着换部门——原部门主管突然看不到历史工单，而且是静默发生的。
        """
        ticket = Ticket.objects.create(title="单", creator=staff, department=depts["cs"])

        staff.department = depts["tech"]
        staff.save()

        ticket.refresh_from_db()
        assert ticket.department == depts["cs"]  # 没跟着变
        assert ticket.creator.department == depts["tech"]

    def test_cannot_forge_creator(self, client, staff, depts, django_user_model):
        """creator / department 不在表单 fields 里，构造 POST 也塞不进去。"""
        victim = django_user_model.objects.create_user(
            username="victim", password="x", department=depts["tech"]
        )
        grant(staff, TicketPerm.VIEW, TicketPerm.CREATE)
        client.force_login(staff)

        client.post(
            reverse("tickets:create"),
            {
                "title": "伪造",
                "priority": 2,
                "status": "open",
                "creator": victim.pk,
                "department": depts["tech"].pk,
            },
        )

        ticket = Ticket.objects.get(title="伪造")
        assert ticket.creator == staff
        assert ticket.department == depts["cs"]


@pytest.mark.django_db
class TestQueryCount:
    def _count_queries(self, client, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(url)
        return len(ctx), resp

    def test_list_avoids_n_plus_one(self, client, staff, depts):
        """列表页的查询数必须与工单条数无关。

        忘了 select_related 的话，40 条工单会额外产生 120 次查询
        （creator / assignee / department 各一次）。
        """
        grant(staff, TicketPerm.VIEW)
        client.force_login(staff)
        url = reverse("tickets:list")

        for i in range(5):
            Ticket.objects.create(title=f"a{i}", creator=staff, department=depts["cs"])
        few, _ = self._count_queries(client, url)

        for i in range(35):
            Ticket.objects.create(title=f"b{i}", creator=staff, department=depts["cs"])
        many, resp = self._count_queries(client, url)

        assert resp.context["page"].paginator.count == 40
        assert few == many, f"查询数随数据量增长：{few} -> {many}，select_related 没生效"

    def test_permission_resolution_is_repeated_three_times(self, client, staff, depts):
        """⚠️ v0.13.0 的已知性能问题，v0.16.0 才解决。

        一次请求里 get_user_perm_codes() 被独立调用了 3 次：
          1. @require_perm 装饰器
          2. 侧边栏菜单树
          3. 模板里的 {% if ... in perms %}

        每次都重新查一遍角色和权限码——因为还没有请求级缓存。
        这就是 v0.6.0 延伸思考 4 让你去实测的那个痛点。
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        grant(staff, TicketPerm.VIEW)
        client.force_login(staff)

        with CaptureQueriesContext(connection) as ctx:
            client.get(reverse("tickets:list"))

        role_lookups = [
            q for q in ctx.captured_queries if 'FROM "rbac_role"' in q["sql"]
        ]
        assert len(role_lookups) >= 3, (
            f"预期至少 3 次重复的权限解析（v0.16.0 的缓存会把它降到 1 次），"
            f"实测 {len(role_lookups)} 次"
        )


@pytest.mark.django_db
class TestDataScopeNowEnforced:
    """v0.13.0 刻意留下的漏洞，在 v0.14.0 被补上——这些断言是翻转过来的。

    对比 v0.13.0 的同名测试（当时叫 TestNoDataScopeYet）：
        count == 8  -> count == 5
        200         -> 404
    """

    def test_staff_no_longer_sees_other_departments(self, client, staff, tickets):
        from apps.rbac.constants import DataScope

        role = grant(staff, TicketPerm.VIEW)
        role.data_scope = DataScope.DEPT_AND_BELOW
        role.save()
        client.force_login(staff)

        resp = client.get(reverse("tickets:list"))

        # v0.13.0 时是 8（含技术部 3 张），现在只剩客服部的 5 张
        assert resp.context["page"].paginator.count == 5
        assert "技术工单0" not in resp.content.decode()

    def test_other_departments_ticket_returns_404(self, client, staff, tickets):
        """范围外返回 404 而不是 403——403 会泄露记录的存在性。"""
        from apps.rbac.constants import DataScope

        role = grant(staff, TicketPerm.VIEW)
        role.data_scope = DataScope.DEPT_AND_BELOW
        role.save()
        client.force_login(staff)

        tech_ticket = Ticket.objects.filter(title__startswith="技术工单").first()
        resp = client.get(reverse("tickets:detail", args=[tech_ticket.pk]))

        assert resp.status_code == 404  # v0.13.0 时是 200
