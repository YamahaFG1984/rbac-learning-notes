"""API 层权限复用（v1.2.0）—— 对整个架构设计的总检验。"""

import csv
import io
import subprocess

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.demo import DEMO_PASSWORD, build_demo_world
from apps.tickets.models import Ticket

User = get_user_model()


@pytest.fixture
def world(db):
    return build_demo_world()


def api_as(username):
    client = APIClient()
    resp = client.post(
        reverse("api:token_obtain_pair"),
        {"username": username, "password": DEMO_PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
    return client


# --------------------------------------------------------------------------- #
# 🎯 第一条验收：services.py 一行都不用改
# --------------------------------------------------------------------------- #


def test_kernel_untouched_between_v1_1_and_v1_2():
    """🎯 本 tag 的核心验收条件（ADR-013）。

        git diff v1.1.0 v1.2.0 -- apps/rbac/services.py

    期望输出为空。如果需要改，说明内核里漏进了表现层的关注点。

    这是一个**可检验的架构承诺**，而不是一句「我们的架构是解耦的」的空话。
    """
    tags = subprocess.run(
        ["git", "tag", "-l", "v1.1.0"], capture_output=True, text=True
    ).stdout.strip()
    if not tags:
        pytest.skip("v1.1.0 尚未打 tag")

    diff = subprocess.run(
        ["git", "diff", "v1.1.0", "HEAD", "--", "apps/rbac/services.py"],
        capture_output=True,
        text=True,
    ).stdout

    assert diff == "", (
        "接入 DRF 时改动了权限内核——ADR-013 的解耦没做到位：\n" + diff[:2000]
    )


def test_hasperm_contains_no_permission_logic():
    """HasPerm 只做翻译，不做判断。两套逻辑必然漂移，漂移处就是漏洞。"""
    import ast
    import inspect

    from apps.rbac.api import permissions

    tree = ast.parse(inspect.getsource(permissions))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    # 不该直接碰模型——那意味着它自己在查权限
    assert "apps.rbac.models" not in imported
    assert "apps.rbac.services" in imported


# --------------------------------------------------------------------------- #
# 🎯 第二条验收：v1.1.0 的漏洞已补
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestHolesFromV110AreClosed:
    """v1.1.0 的 TestNoAuthorizationYet 三条断言，在这里全部翻转。"""

    def test_no_role_can_no_longer_delete(self, world):
        client = api_as("no_role")
        victim = Ticket.objects.filter(department=world["tech"]).first()

        resp = client.delete(f"/api/v1/tickets/{victim.pk}/")

        assert resp.status_code == 403  # v1.1.0 时是 204
        assert Ticket.objects.filter(pk=victim.pk).exists()

    @pytest.mark.parametrize(
        "username,expected",
        [("superadmin", 80), ("sysadmin", 80), ("cs_manager", 50), ("cs_staff", 5)],
    )
    def test_ticket_count_now_scoped(self, world, username, expected):
        """v1.1.0 时所有人都是 80。"""
        count = api_as(username).get("/api/v1/tickets/").json()["count"]
        assert count == expected

    def test_no_role_cannot_list_users_or_roles(self, world):
        client = api_as("no_role")
        assert client.get("/api/v1/users/").status_code == 403  # v1.1.0 时是 200
        assert client.get("/api/v1/roles/").status_code == 403


# --------------------------------------------------------------------------- #
# 🎯 第三条验收：API 与 Web 行为完全一致
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestApiWebConsistency:
    @pytest.mark.parametrize(
        "username,expected", [("cs_manager", 50), ("cs_staff", 5), ("sysadmin", 80)]
    )
    def test_same_user_same_count_both_paths(self, client, world, username, expected):
        """同一个用户，走两条路径，结果必须相同——不能对不上账。"""
        client.force_login(world[username])
        web_count = client.get(reverse("tickets:list")).context["page"].paginator.count

        api_count = api_as(username).get("/api/v1/tickets/").json()["count"]

        assert web_count == api_count == expected

    def test_perms_identical_to_template_layer(self, world):
        """/auth/profile 的 perms 与模板层 get_user_perm_codes 一致
        ——因为它们调的是同一个函数。"""
        from apps.rbac.services import get_user_perm_codes

        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        kernel_codes = sorted(get_user_perm_codes(world["cs_manager"]))

        assert payload["perms"] == kernel_codes

    def test_menus_structurally_identical_to_sidebar(self, world):
        """API 的菜单树与模板层来自**同一个** get_user_menu_tree()。

        ⚠️ 不能断言字典全等：fe-v0.5.0 起 API 层会额外补上
           routePath / component 两个 SPA 专用字段（F-ADR-008）。
           那两个字段刻意**不进内核**——模板版用不上它们。

        所以这里断言的是「结构一致」：同样的节点、同样的层级、同样的顺序。
        这才是这条测试真正要守的东西。
        """
        from apps.rbac.services import get_user_menu_tree

        def shape(nodes):
            return [
                {"id": n["id"], "name": n["name"], "children": shape(n["children"])}
                for n in nodes
            ]

        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        assert shape(payload["menus"]) == shape(get_user_menu_tree(world["cs_manager"]))

    def test_api_menus_carry_spa_route_fields(self, world):
        """SPA 需要的前端路由字段由 API 层补上，不在内核里（F-ADR-008）。"""
        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        leaf = payload["menus"][0]["children"][0]
        assert leaf["routePath"] == "/tickets"
        assert leaf["component"] == "tickets/List"

        # 内核的返回值里**没有**这两个字段
        from apps.rbac.services import get_user_menu_tree

        kernel_leaf = get_user_menu_tree(world["cs_manager"])[0]["children"][0]
        assert "routePath" not in kernel_leaf
        assert "component" not in kernel_leaf


# --------------------------------------------------------------------------- #
# IDOR：范围外 404
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestApiIdor:
    @pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
    def test_out_of_scope_returns_404(self, world, method):
        """DRF 的 get_object() 走 get_queryset()，所以重写一处
        就同时保护了详情/更新/删除——不会出现「只挡住列表」的疏漏。"""
        client = api_as("cs_manager")
        tech_ticket = Ticket.objects.filter(department=world["tech"]).first()

        resp = getattr(client, method)(
            f"/api/v1/tickets/{tech_ticket.pk}/", {}, format="json"
        )

        assert resp.status_code == 404

    def test_in_scope_is_reachable(self, world):
        client = api_as("cs_manager")
        own = Ticket.objects.filter(department=world["cs1"]).first()
        assert client.get(f"/api/v1/tickets/{own.pk}/").status_code == 200


# --------------------------------------------------------------------------- #
# 默认拒绝
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDenyByDefault:
    def test_missing_perm_map_entry_denies(self, world, monkeypatch):
        """⚠️ 漏配 perm_map = 403，不是静默放行。

        自定义 @action 是漏配的重灾区——它们不在标准 CRUD 列表里。
        """
        from apps.tickets.api.views import TicketViewSet

        pruned = {k: v for k, v in TicketViewSet.perm_map.items() if k != "destroy"}
        monkeypatch.setattr(TicketViewSet, "perm_map", pruned)

        client = api_as("cs_manager")
        own = Ticket.objects.filter(department=world["cs1"]).first()

        assert client.delete(f"/api/v1/tickets/{own.pk}/").status_code == 403

    def test_w002_check_catches_missing_entries(self, monkeypatch):
        """rbac.W002 —— rbac.W001 在 API 层的对应物。"""
        from apps.rbac.checks import check_viewset_perm_maps
        from apps.tickets.api.views import TicketViewSet

        assert check_viewset_perm_maps(None) == []

        pruned = {k: v for k, v in TicketViewSet.perm_map.items() if k != "destroy"}
        monkeypatch.setattr(TicketViewSet, "perm_map", pruned)

        problems = check_viewset_perm_maps(None)
        assert any(p.id == "rbac.W002" and "destroy" in p.msg for p in problems)

    def test_permission_endpoint_is_readonly(self, world):
        """权限点由代码声明，不允许 API 改（ADR-004）。"""
        client = api_as("superadmin")
        resp = client.post(
            "/api/v1/permissions/", {"code": "evil:evil:view", "name": "坏的"},
            format="json",
        )
        assert resp.status_code == 405


# --------------------------------------------------------------------------- #
# profile 接口
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestProfile:
    def test_shape(self, world):
        payload = api_as("cs_manager").get(reverse("api:profile")).json()

        assert payload["user"]["username"] == "cs_manager"
        assert payload["user"]["department"]["name"] == "客服部"
        assert payload["user"]["isSuperuser"] is False
        assert "ticket:ticket:view" in payload["perms"]
        assert isinstance(payload["menus"], list)

    def test_superuser_uses_wildcard(self, world):
        """ALL_PERMS 哨兵不可序列化，用 ["*"] 表示全部放行。
        这一点必须和前端约定好。"""
        payload = api_as("superadmin").get(reverse("api:profile")).json()
        assert payload["perms"] == ["*"]
        assert payload["user"]["isSuperuser"] is True

    def test_inherited_perms_included(self, world):
        """客服主管继承客服专员——profile 返回的是展开后的有效权限。"""
        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        assert "ticket:ticket:create" in payload["perms"]  # 继承自专员
        assert "ticket:ticket:delete" in payload["perms"]  # 主管自己的

    def test_requires_authentication(self):
        assert APIClient().get(reverse("api:profile")).status_code == 401


# --------------------------------------------------------------------------- #
# 列表筛选与导出（v1.3.0，SPA 的工单列表需要）
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestListAndExport:
    """两个前端共用一套筛选 + 一套导出，必须筛得完全一致。"""

    @pytest.mark.parametrize(
        "username,expected",
        [("superadmin", 80), ("sysadmin", 80), ("cs_manager", 50), ("cs_staff", 5)],
    )
    def test_list_count_matches_scope_matrix(self, world, username, expected):
        """count 必须与后端数据权限矩阵一致——前端只是把 results 渲染出来，
        任何一层多做了事，这里的数字就对不上。"""
        resp = api_as(username).get("/api/v1/tickets/")
        assert resp.json()["count"] == expected

    def test_filters_narrow_the_scoped_queryset(self, world):
        """筛选作用在**已经过数据权限过滤**的结果上，不是反过来。"""
        client = api_as("cs_manager")
        total = client.get("/api/v1/tickets/").json()["count"]
        filtered = client.get("/api/v1/tickets/?status=open").json()["count"]
        assert 0 < filtered <= total

    def test_filter_cannot_widen_scope(self, world):
        """⚠️ 关键：任何筛选参数都不能让用户看到范围外的数据。
        筛选是收窄，永远不可能放宽。"""
        client = api_as("cs_staff")
        for qs in ["", "?status=open", "?priority=1", "?kw=", "?kw=单"]:
            assert client.get(f"/api/v1/tickets/{qs}").json()["count"] <= 5

    def test_export_row_count_equals_list_count(self, world):
        """🎯 导出是最容易被忽略的越权入口：它是后加的功能，
        代码路径和列表页不同。API 版新增后这个风险翻倍了。"""
        client = api_as("cs_manager")
        list_count = client.get("/api/v1/tickets/").json()["count"]

        resp = client.get("/api/v1/tickets/export/")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        assert len([r for r in rows[1:] if r]) == list_count == 50

    def test_export_respects_filters(self, world):
        client = api_as("cs_manager")
        list_count = client.get("/api/v1/tickets/?status=open").json()["count"]

        resp = client.get("/api/v1/tickets/export/?status=open")
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        assert len([r for r in rows[1:] if r]) == list_count

    def test_export_requires_its_own_perm(self, world):
        """cs_staff 有 view 没有 export —— 列表能看，导出不行。"""
        client = api_as("cs_staff")
        assert client.get("/api/v1/tickets/").status_code == 200
        assert client.get("/api/v1/tickets/export/").status_code == 403

    def test_two_frontends_export_identically(self, world, client):
        """模板版和 API 版的导出必须**逐字节相同**。

        这条测试守的是 export.py / filters.py 这次抽取的意义：
        哪天有人只改了其中一个入口，这里立刻红。
        """
        user = User.objects.get(username="cs_manager")
        client.force_login(user)
        web = client.get(reverse("tickets:export")).content

        api = api_as("cs_manager").get("/api/v1/tickets/export/").content
        assert web == api


# --------------------------------------------------------------------------- #
# 派单：候选人列表的越权（v1.3.0 补的一个真实漏洞）
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestAssign:
    """🔴 一个「不该看到用户列表」的人，通过派单下拉框看到了用户列表。

    这类漏洞不出现在权限矩阵里——矩阵测的是接口，而它藏在一个表单控件里。
    """

    def test_assignable_users_is_scoped_to_own_subtree(self, world):
        """cs_manager 在客服部，只该看到客服部及其子部门的人。"""
        payload = api_as("cs_manager").get(
            "/api/v1/tickets/assignable-users/"
        ).json()
        names = {u["username"] for u in payload}

        assert names == {"cs_manager", "cs_staff", "no_role"}
        # 技术部的人和总部的超管都不在里面
        assert "techie" not in names
        assert "superadmin" not in names

    def test_assignable_users_needs_only_assign_perm(self, world):
        """cs_manager **没有** system:user:view，但拿得到候选人列表。

        反过来说：这个接口如果复用 /api/v1/users/，
        就等于强迫「能派单的人」都得有「用户管理」权限——
        权限点被业务需求倒逼着变粗，是权限模型腐化的典型路径。
        """
        client = api_as("cs_manager")
        assert client.get("/api/v1/users/").status_code == 403
        assert client.get("/api/v1/tickets/assignable-users/").status_code == 200

    def test_assignable_users_does_not_leak_contact_info(self, world):
        """只返回下拉框需要的字段，不带手机号 / 邮箱。

        接口返回的字段量应该由调用方的需要决定，
        不是由「手边正好有一个 UserSerializer」决定。
        """
        payload = api_as("cs_manager").get(
            "/api/v1/tickets/assignable-users/"
        ).json()
        assert set(payload[0]) == {"id", "username", "real_name", "department_name"}

    def test_assign_requires_assign_perm(self, world):
        """cs_staff 有 update 没有 assign。"""
        ticket = Ticket.objects.filter(creator__username="cs_staff").first()
        resp = api_as("cs_staff").post(
            f"/api/v1/tickets/{ticket.pk}/assign/", {"assignee": None}, format="json"
        )
        assert resp.status_code == 403

    def test_assign_out_of_scope_ticket_is_404(self, world):
        """技术部的工单不在 cs_manager 的数据范围内 —— 404 不是 403。"""
        ticket = Ticket.objects.filter(department__code="TECH").first()
        resp = api_as("cs_manager").post(
            f"/api/v1/tickets/{ticket.pk}/assign/", {"assignee": None}, format="json"
        )
        assert resp.status_code == 404

    def test_cannot_assign_to_user_outside_scope(self, world):
        """🔴 下拉框只列了范围内的人，但攻击者可以直接提交任意 id。

        下拉框不是安全边界 —— 和「隐藏按钮不是安全边界」是同一句话。
        """
        ticket = Ticket.objects.filter(department__code="CS1").first()
        techie = User.objects.get(username="techie")

        resp = api_as("cs_manager").post(
            f"/api/v1/tickets/{ticket.pk}/assign/",
            {"assignee": techie.pk},
            format="json",
        )
        assert resp.status_code == 400
        assert "assignee" in resp.json()

    def test_assign_succeeds_within_scope(self, world):
        ticket = Ticket.objects.filter(department__code="CS1").first()
        staff = User.objects.get(username="cs_staff")

        resp = api_as("cs_manager").post(
            f"/api/v1/tickets/{ticket.pk}/assign/",
            {"assignee": staff.pk},
            format="json",
        )
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.assignee_id == staff.pk


@pytest.mark.django_db
class TestTemplateAssignFormIsScopedToo:
    """同一条规则必须在**两个前端**都生效。

    v0.15.0 的 TicketAssignForm 用了 ModelForm 的默认 queryset（= 全部用户），
    修的时候如果只修 API 那一侧，模板版的泄露就留在原地了。
    """

    def test_template_form_uses_same_candidate_set(self, world):
        from apps.tickets.forms import TicketAssignForm, TicketForm

        actor = User.objects.get(username="cs_manager")
        expected = {"cs_manager", "cs_staff", "no_role"}

        for form_cls in (TicketAssignForm, TicketForm):
            qs = form_cls(actor=actor).fields["assignee"].queryset
            assert {u.username for u in qs} == expected, form_cls.__name__

    def test_without_actor_it_falls_back_to_empty_not_everyone(self, world):
        """🔴 忘了传 actor 时，兜底是**空集**而不是全部用户。

        actor 是可选参数（ModelForm 在很多地方会被无参实例化）。
        兜底如果是「全部用户」，那么任何一个忘记传 actor 的调用点
        都会**悄无声息地**退回 v0.15.0 的泄露。

        空下拉框会立刻被人发现并报 bug；全量下拉框不会——
        没有人会因为「选项太多」去提工单。

        这就是「默认值指向出错后果最轻的方向」在表单上的形态，
        同 data_scope 默认 SELF_ONLY、build_scope_q 的四处 Q(pk__in=[])。
        """
        from apps.tickets.forms import TicketAssignForm, TicketForm

        assert User.objects.count() == 6
        for form_cls in (TicketAssignForm, TicketForm):
            assert form_cls().fields["assignee"].queryset.count() == 0
