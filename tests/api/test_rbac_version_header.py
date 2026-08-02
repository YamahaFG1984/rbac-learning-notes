"""X-RBAC-Version 响应头（v1.3.0，SPA 感知权限变更用）。"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.demo import DEMO_PASSWORD, build_demo_world
from apps.rbac.cache import get_version
from apps.rbac.models import Permission, RolePermission, Role
from apps.tickets.permissions import TicketPerm

HEADER = "X-RBAC-Version"


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


@pytest.mark.django_db
class TestVersionHeader:
    def test_api_responses_carry_the_header(self, world):
        resp = api_as("cs_manager").get("/api/v1/tickets/")
        assert resp[HEADER] == str(get_version())

    def test_header_changes_after_a_permission_change(self, world):
        """🔴 这是整个机制的核心：改权限 → 版本号变 → 前端下一次响应就知道了。"""
        client = api_as("cs_manager")
        before = client.get("/api/v1/tickets/")[HEADER]

        role = Role.objects.get(code="cs_manager")
        RolePermission.objects.filter(
            role=role, permission__code=TicketPerm.DELETE
        ).delete()

        after = client.get("/api/v1/tickets/")[HEADER]
        assert after != before

    def test_error_responses_carry_it_too(self, world):
        """⚠️ 错误响应也要带 —— 而且这恰恰是最需要它的时候。

        权限刚被撤销时，用户碰到的第一个响应往往就是 403。
        只在 2xx 上带的话，那一刻正好感知不到。
        """
        resp = api_as("cs_staff").get("/api/v1/tickets/export/")
        assert resp.status_code == 403
        assert HEADER in resp

    def test_unauthenticated_responses_carry_it_too(self):
        resp = APIClient().get("/api/v1/tickets/")
        assert resp.status_code == 401
        assert HEADER in resp

    def test_template_pages_do_not_carry_it(self, world, client):
        """模板版每次请求都重算权限，给它加这个头没有意义，只增加体积。"""
        client.force_login(world["cs_manager"])
        resp = client.get(reverse("tickets:list"))
        assert resp.status_code == 200
        assert HEADER not in resp

    def test_version_is_stable_when_nothing_changes(self, world):
        """没变就不该变 —— 否则前端每个请求都会重拉一次 profile。"""
        client = api_as("cs_manager")
        first = client.get("/api/v1/tickets/")[HEADER]
        second = client.get("/api/v1/tickets/")[HEADER]
        third = client.get(reverse("api:profile"))[HEADER]
        assert first == second == third

    def test_any_permission_change_bumps_it(self, world):
        """全局版本号是**粗粒度**的（ADR-010 的已知取舍）：
        改任何角色都会 bump，所有在线用户都会重拉一次 profile。

        前端因此不能一律提示「你的权限已更新」——那对绝大多数人是误报。
        """
        client = api_as("cs_manager")
        before = client.get("/api/v1/tickets/")[HEADER]

        # 改的是**别人**的角色
        other = Role.objects.get(code="empty")
        RolePermission.objects.create(
            role=other, permission=Permission.objects.get(code=TicketPerm.VIEW)
        )

        assert client.get("/api/v1/tickets/")[HEADER] != before
