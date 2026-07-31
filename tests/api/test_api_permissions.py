"""API 层权限复用（v1.2.0）—— 对整个架构设计的总检验。"""

import subprocess

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.demo import DEMO_PASSWORD, build_demo_world
from apps.tickets.models import Ticket


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

    def test_menus_identical_to_sidebar(self, world):
        from apps.rbac.services import get_user_menu_tree

        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        assert payload["menus"] == get_user_menu_tree(world["cs_manager"])


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
        assert payload["user"]["is_superuser"] is False
        assert "ticket:ticket:view" in payload["perms"]
        assert isinstance(payload["menus"], list)

    def test_superuser_uses_wildcard(self, world):
        """ALL_PERMS 哨兵不可序列化，用 ["*"] 表示全部放行。
        这一点必须和前端约定好。"""
        payload = api_as("superadmin").get(reverse("api:profile")).json()
        assert payload["perms"] == ["*"]
        assert payload["user"]["is_superuser"] is True

    def test_inherited_perms_included(self, world):
        """客服主管继承客服专员——profile 返回的是展开后的有效权限。"""
        payload = api_as("cs_manager").get(reverse("api:profile")).json()
        assert "ticket:ticket:create" in payload["perms"]  # 继承自专员
        assert "ticket:ticket:delete" in payload["perms"]  # 主管自己的

    def test_requires_authentication(self):
        assert APIClient().get(reverse("api:profile")).status_code == 401
