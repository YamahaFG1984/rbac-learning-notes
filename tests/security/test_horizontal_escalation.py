"""水平越权 / IDOR：访问同级别他人的数据。

v0.15.0 实现，v0.18.0 归入 tests/security/ 统一管理——
安全测试和功能测试分开，是为了能单独跑、单独看覆盖情况：

    pytest tests/security/ -v
"""

import csv
import io

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Department
from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role, RoleDepartment, RolePermission, UserRole
from apps.rbac.services import get_role_custom_dept_ids, save_role_departments
from apps.tickets.models import Ticket
from apps.tickets.permissions import TicketPerm


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


@pytest.fixture
def org(db):
    hq = Department.objects.create(code="HQ", name="总部")
    cs = Department.objects.create(code="CS", name="客服部", parent=hq)
    cs1 = Department.objects.create(code="CS1", name="客服一组", parent=cs)
    tech = Department.objects.create(code="TECH", name="技术部", parent=hq)
    mkt = Department.objects.create(code="MKT", name="市场部", parent=hq)
    return {"hq": hq, "cs": cs, "cs1": cs1, "tech": tech, "mkt": mkt}


@pytest.fixture
def world(org, django_user_model, perms):
    staff = django_user_model.objects.create_user(
        username="cs_staff", password="x", department=org["cs1"]
    )
    techie = django_user_model.objects.create_user(
        username="techie", password="x", department=org["tech"]
    )
    mine = Ticket.objects.create(title="我的单", creator=staff, department=org["cs1"])
    theirs = Ticket.objects.create(title="技术部的单", creator=techie, department=org["tech"])
    mkt_ticket = Ticket.objects.create(title="市场部的单", creator=techie, department=org["mkt"])
    return {
        "staff": staff,
        "techie": techie,
        "mine": mine,
        "theirs": theirs,
        "mkt_ticket": mkt_ticket,
        **org,
    }


def grant_all_ticket_perms(user, scope=DataScope.SELF_ONLY):
    role = Role.objects.create(code=f"r{user.pk}", name="r", data_scope=scope)
    for code in [
        TicketPerm.VIEW,
        TicketPerm.UPDATE,
        TicketPerm.DELETE,
        TicketPerm.ASSIGN,
        TicketPerm.EXPORT,
    ]:
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code=code)
        )
    UserRole.objects.create(user=user, role=role)
    return role


# --------------------------------------------------------------------------- #
# 🔴 IDOR：范围外一律 404，不是 403
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestIdor:
    @pytest.fixture(autouse=True)
    def setup(self, client, world):
        grant_all_ticket_perms(world["staff"])
        client.force_login(world["staff"])
        self.client = client
        self.world = world

    @pytest.mark.parametrize(
        "url_name,method",
        [
            ("tickets:detail", "get"),
            ("tickets:update", "get"),
            ("tickets:update", "post"),  # ⚠️ POST 单独测——只挡 GET 是常见疏漏
            ("tickets:delete", "post"),
            ("tickets:assign", "get"),
            ("tickets:assign", "post"),
        ],
    )
    def test_out_of_scope_returns_404(self, url_name, method):
        """范围外返回 404 而不是 403。

        403 的含义是「这东西存在，但你没权限」——泄露了记录的存在性。
        攻击者可以遍历 ID，用 403/404 的差异画出整个数据库的 ID 分布。
        """
        url = reverse(url_name, args=[self.world["theirs"].pk])
        resp = getattr(self.client, method)(url, {})
        assert resp.status_code == 404, f"{method.upper()} {url} 返回了 {resp.status_code}"

    def test_own_ticket_is_reachable(self):
        resp = self.client.get(reverse("tickets:detail", args=[self.world["mine"].pk]))
        assert resp.status_code == 200

    def test_delete_post_does_not_destroy_data(self):
        self.client.post(reverse("tickets:delete", args=[self.world["theirs"].pk]))
        assert Ticket.objects.filter(pk=self.world["theirs"].pk).exists()

    def test_update_post_does_not_modify_data(self):
        self.client.post(
            reverse("tickets:update", args=[self.world["theirs"].pk]),
            {"title": "被改了", "priority": 3, "status": "closed"},
        )
        self.world["theirs"].refresh_from_db()
        assert self.world["theirs"].title == "技术部的单"

    def test_nonexistent_id_indistinguishable_from_out_of_scope(self):
        """不存在的 ID 和范围外的 ID 必须给出相同的响应——否则仍可探测。"""
        out_of_scope = self.client.get(
            reverse("tickets:detail", args=[self.world["theirs"].pk])
        )
        nonexistent = self.client.get(reverse("tickets:detail", args=[999999]))
        assert out_of_scope.status_code == nonexistent.status_code == 404


# --------------------------------------------------------------------------- #
# 自定义部门范围
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestCustomScope:
    def test_custom_includes_subtree(self, world, org):
        """勾选「客服部」应包含客服一组——管理员的意图几乎肯定是含下级。"""
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.CUSTOM)
        RoleDepartment.objects.create(role=role, department=org["cs"])
        UserRole.objects.create(user=world["techie"], role=role)

        assert get_role_custom_dept_ids(role) == {org["cs"].id, org["cs1"].id}
        assert Ticket.objects.for_user(world["techie"]).count() == 1  # 客服一组那张

    def test_custom_with_no_department_returns_empty(self, world):
        """选了 CUSTOM 却一个部门都没勾 -> 空集，不是全集。"""
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.CUSTOM)
        UserRole.objects.create(user=world["techie"], role=role)
        assert Ticket.objects.for_user(world["techie"]).count() == 0

    def test_union_with_custom_does_not_lose_data(self, world, org):
        """🔴 「取最宽枚举」在这里会丢数据。

        staff 有两个角色：
          A = SELF_ONLY(4)               -> 自己创建的 1 张（客服一组）
          B = CUSTOM(5)，勾选市场部       -> 市场部的 1 张

        按编号取最宽会选 SELF_ONLY(4)，结果只有 1 张——丢掉了市场部那张。
        真并集才是 2 张。
        """
        staff = world["staff"]
        a = Role.objects.create(code="a", name="a", data_scope=DataScope.SELF_ONLY)
        b = Role.objects.create(code="b", name="b", data_scope=DataScope.CUSTOM)
        RoleDepartment.objects.create(role=b, department=org["mkt"])
        UserRole.objects.create(user=staff, role=a)
        UserRole.objects.create(user=staff, role=b)

        visible = set(Ticket.objects.for_user(staff).values_list("title", flat=True))
        assert visible == {"我的单", "市场部的单"}

    def test_save_ignores_departments_when_scope_is_not_custom(self, world, org):
        """后端不信任前端的显隐控制。

        用户选了 SELF_ONLY 却提交一堆部门 ID，必须忽略——否则一旦有人
        把 scope 改成 CUSTOM，就会出现意外的范围。
        """
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.SELF_ONLY)
        saved = save_role_departments(role, [org["mkt"].id, org["tech"].id])
        assert saved == set()
        assert RoleDepartment.objects.filter(role=role).count() == 0

    def test_save_rejects_unknown_department_ids(self, world, org):
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.CUSTOM)
        saved = save_role_departments(role, [org["mkt"].id, 999999])
        assert saved == {org["mkt"].id}

    def test_query_count_independent_of_selection_size(
        self, world, org, django_assert_num_queries
    ):
        role = Role.objects.create(code="c", name="c", data_scope=DataScope.CUSTOM)
        for d in (org["cs"], org["tech"], org["mkt"]):
            RoleDepartment.objects.create(role=role, department=d)
        # 2 = 取勾选部门的 path + 按 path 前缀取全部子树
        with django_assert_num_queries(2):
            get_role_custom_dept_ids(role)


# --------------------------------------------------------------------------- #
# 导出
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestExport:
    def test_export_is_scoped(self, client, world):
        """导出是最容易被忽略的越权入口——它通常是后加的功能，
        代码路径也和列表页不同。验收标准：行数 == 列表页总数。"""
        grant_all_ticket_perms(world["staff"])
        client.force_login(world["staff"])

        list_count = client.get(reverse("tickets:list")).context["page"].paginator.count
        resp = client.get(reverse("tickets:export"))

        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        data_rows = [r for r in rows[1:] if r]

        assert len(data_rows) == list_count == 1
        assert "技术部的单" not in resp.content.decode("utf-8-sig")

    def test_export_requires_its_own_perm(self, client, world):
        role = Role.objects.create(code="r", name="r", data_scope=DataScope.ALL)
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code=TicketPerm.VIEW)
        )
        UserRole.objects.create(user=world["staff"], role=role)
        client.force_login(world["staff"])

        assert client.get(reverse("tickets:export")).status_code == 403
