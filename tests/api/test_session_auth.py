"""Session 认证通道（F-ADR-003）与 CSRF（F-ADR-004）。

两条认证通道并存：SPA 走 Session，第三方走 Bearer JWT。
两条都要测——只测一条的话，另一条坏了没人知道。
"""

import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.common.demo import DEMO_PASSWORD, build_demo_world


@pytest.fixture
def world(db):
    return build_demo_world()


@pytest.fixture
def api():
    """enforce_csrf_checks=True —— 默认的 APIClient 会跳过 CSRF，
    那样就测不到真实行为了。"""
    return APIClient(enforce_csrf_checks=True)


def get_csrf(api) -> str:
    api.get(reverse("api:csrf"))
    return api.cookies["csrftoken"].value


def login(api, username, password=DEMO_PASSWORD):
    token = get_csrf(api)
    return api.post(
        reverse("api:login"),
        {"username": username, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )


# --------------------------------------------------------------------------- #
# Session 通道
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSessionChannel:
    def test_login_returns_profile_payload(self, api, world):
        resp = login(api, "cs_manager")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["username"] == "cs_manager"
        assert "ticket:ticket:view" in body["perms"]
        assert isinstance(body["menus"], list)

    def test_session_cookie_is_httponly(self, api, world):
        """F-ADR-002 的核心：真正的凭证 JS 读不到。"""
        login(api, "cs_manager")
        session = api.cookies["sessionid"]
        assert session["httponly"] is True

    def test_csrf_cookie_is_not_httponly(self, api, world):
        """F-ADR-004：CSRF token 必须能被 JS 读到，否则 SPA 发不出写请求。

        这不是安全倒退——CSRF token 本来就不是秘密，
        它只需要「攻击者的站点读不到」，而同源策略已经保证了。
        """
        get_csrf(api)
        assert not api.cookies["csrftoken"]["httponly"]

    def test_read_request_with_session_only(self, api, world):
        """没有 Authorization 头，纯靠 Cookie。"""
        login(api, "cs_manager")
        resp = api.get("/api/v1/tickets/")
        assert resp.status_code == 200
        assert resp.json()["count"] == 50

    def test_write_request_with_csrf(self, api, world):
        login(api, "cs_manager")
        token = api.cookies["csrftoken"].value
        ticket = world_ticket(world, "cs1")

        resp = api.delete(f"/api/v1/tickets/{ticket.pk}/", HTTP_X_CSRFTOKEN=token)

        assert resp.status_code == 204

    def test_write_request_without_csrf_is_rejected(self, api, world):
        """DRF 的 SessionAuthentication 强制 CSRF 检查——这是刻意设计。"""
        login(api, "cs_manager")
        ticket = world_ticket(world, "cs1")

        resp = api.delete(f"/api/v1/tickets/{ticket.pk}/")

        assert resp.status_code == 403

    def test_logout_invalidates_session(self, api, world):
        login(api, "cs_manager")
        token = api.cookies["csrftoken"].value

        assert api.post(reverse("api:logout"), HTTP_X_CSRFTOKEN=token).status_code == 204
        assert api.get("/api/v1/tickets/").status_code == 401

    def test_csrf_token_rotates_on_login(self, api, world):
        """登录前拿到的 token 在登录后不该还有效——较弱的会话固定变体。"""
        before = get_csrf(api)
        api.post(
            reverse("api:login"),
            {"username": "cs_manager", "password": DEMO_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=before,
        )
        after = api.cookies["csrftoken"].value
        assert after != before


# --------------------------------------------------------------------------- #
# 401 vs 403 —— F-ADR-011 的后端一半
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestStatusCodeSemantics:
    def test_unauthenticated_returns_401_not_403(self, api, world):
        """🔴 加上 SessionAuthentication 后，DRF 默认会把 401 降级成 403
        （因为 SessionAuthentication.authenticate_header() 返回 None）。

        这对 SPA 是致命的：前端分不清「没登录」和「没权限」，
        用户会永远停在「权限不足」上，而真实原因是他该去登录。

        我们用自定义 exception handler 显式表达语义。
        """
        resp = api.get("/api/v1/tickets/")
        assert resp.status_code == 401

    def test_authenticated_but_no_permission_returns_403(self, api, world):
        login(api, "no_role")
        resp = api.get("/api/v1/tickets/")
        assert resp.status_code == 403

    def test_login_failure_returns_400_not_401(self, api, world):
        """400 而不是 401——401 会让前端跳登录页，而用户已经在登录页了。"""
        resp = login(api, "cs_manager", "wrong-password")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "用户名或密码错误"


# --------------------------------------------------------------------------- #
# 与 v0.7.0 的业务规则复用
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestReusesExistingRules:
    @pytest.fixture(autouse=True)
    def _clear(self):
        cache.clear()
        yield
        cache.clear()

    def test_lockout_is_shared_with_web_channel(self, api, world, client):
        """🔴 Web 侧锁定后，API 侧也必须被锁。

        不复用 v0.7.0 的计数器就会出现「Web 登录被锁了，API 还能接着试」
        ——那是真漏洞。
        """
        for _ in range(settings.LOGIN_FAIL_MAX_ATTEMPTS):
            client.post(
                reverse("accounts:login"),
                {"username": "cs_manager", "password": "wrong"},
            )

        resp = login(api, "cs_manager")  # 用**正确**密码
        assert resp.status_code == 429

    def test_login_writes_audit_log(self, api, world):
        login(api, "cs_manager")
        entry = AuditLog.objects.filter(action=AuditAction.LOGIN).first()
        assert entry is not None
        assert entry.detail["channel"] == "api"

    def test_failed_login_writes_audit_log(self, api, world):
        login(api, "cs_manager", "wrong")
        entry = AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).first()
        assert entry.actor is None
        assert entry.detail["username"] == "cs_manager"

    def test_inactive_user_cannot_login(self, api, world, django_user_model):
        django_user_model.objects.filter(username="cs_manager").update(is_active=False)
        assert login(api, "cs_manager").status_code == 400


# --------------------------------------------------------------------------- #
# JWT 通道仍然可用
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestJwtChannelStillWorks:
    def test_bearer_token_read(self, world):
        client = APIClient(enforce_csrf_checks=True)
        token = client.post(
            reverse("api:token_obtain_pair"),
            {"username": "cs_manager", "password": DEMO_PASSWORD},
            format="json",
        ).json()["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        assert client.get("/api/v1/tickets/").status_code == 200

    def test_bearer_write_needs_no_csrf(self, world):
        """Bearer 不受 CSRF 约束——CSRF 攻击的前提是「浏览器自动带凭证」，
        而 Authorization 头不会被自动带上。"""
        client = APIClient(enforce_csrf_checks=True)
        token = client.post(
            reverse("api:token_obtain_pair"),
            {"username": "cs_manager", "password": DEMO_PASSWORD},
            format="json",
        ).json()["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        ticket = world_ticket(world, "cs1")
        assert client.delete(f"/api/v1/tickets/{ticket.pk}/").status_code == 204


def world_ticket(world, dept_key):
    from apps.tickets.models import Ticket

    return Ticket.objects.filter(department=world[dept_key]).first()
