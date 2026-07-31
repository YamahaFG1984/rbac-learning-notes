"""JWT 认证（v1.1.0）。"""

import pytest
from django.urls import reverse

from apps.common.demo import DEMO_PASSWORD, build_demo_world
from apps.tickets.models import Ticket


@pytest.fixture
def world(db):
    return build_demo_world()


@pytest.fixture
def api(client):
    from rest_framework.test import APIClient

    return APIClient()


def get_token(api, username, password=DEMO_PASSWORD):
    resp = api.post(
        reverse("api:token_obtain_pair"),
        {"username": username, "password": password},
        format="json",
    )
    return resp


@pytest.mark.django_db
class TestTokenIssuing:
    def test_valid_credentials(self, api, world):
        resp = get_token(api, "cs_staff")
        assert resp.status_code == 200
        assert "access" in resp.json()
        assert "refresh" in resp.json()

    def test_wrong_password(self, api, world):
        assert get_token(api, "cs_staff", "wrong").status_code == 401

    def test_inactive_user(self, api, world, django_user_model):
        django_user_model.objects.filter(username="cs_staff").update(is_active=False)
        assert get_token(api, "cs_staff").status_code == 401

    def test_refresh(self, api, world):
        refresh = get_token(api, "cs_staff").json()["refresh"]
        resp = api.post(
            reverse("api:token_refresh"), {"refresh": refresh}, format="json"
        )
        assert resp.status_code == 200
        assert "access" in resp.json()


@pytest.mark.django_db
class TestAuthenticatedAccess:
    def test_with_token(self, api, world):
        token = get_token(api, "cs_staff").json()["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert api.get("/api/v1/tickets/").status_code == 200

    def test_without_token_returns_401_not_302(self, api, world):
        """API 未认证必须返回 401 JSON，不是 302 跳登录页
        ——API 客户端收到一个 HTML 登录页是没法处理的。"""
        resp = api.get("/api/v1/tickets/")
        assert resp.status_code == 401
        assert resp["Content-Type"].startswith("application/json")

    def test_garbage_token(self, api, world):
        api.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        assert api.get("/api/v1/tickets/").status_code == 401


@pytest.mark.django_db
class TestJwtRevocationGap:
    def test_disabled_user_token_is_rejected(self, api, world, django_user_model):
        """⚠️ JWT 的「无状态」在实际实现里往往是打折的。

        理论上签发出去的 token 在过期前无法撤销。但 simplejwt 的
        JWTAuthentication 每次请求都会查库取 user（request.user 需要真实对象），
        并走 USER_AUTHENTICATION_RULE 检查 is_active。

        所以禁用用户**其实会被挡住**——代价是牺牲了「无状态」。
        这正是 JWT 最重要的认知点：无状态和可撤销性之间必须选一个。
        """
        token = get_token(api, "cs_staff").json()["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert api.get("/api/v1/tickets/").status_code == 200

        django_user_model.objects.filter(username="cs_staff").update(is_active=False)

        assert api.get("/api/v1/tickets/").status_code == 401

    def test_token_payload_does_not_contain_permissions(self, api, world):
        """⚠️ 绝不能把权限列表塞进 JWT payload。

        · payload 是 base64，**不是加密**，任何人都能解开看
        · token 里的权限是签发时的快照，改了角色也没用，直到过期
        · 200 个权限码几 KB，每个请求都要带

        权限必须在服务端实时判断（v1.2.0）。
        """
        import base64
        import json

        token = get_token(api, "cs_manager").json()["access"]
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        as_text = json.dumps(payload)
        assert "ticket:ticket" not in as_text
        assert "perms" not in payload


@pytest.mark.django_db
class TestSerializerWhitelist:
    def test_user_serializer_hides_sensitive_fields(self, api, world):
        token = get_token(api, "superadmin").json()["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        row = api.get("/api/v1/users/").json()["results"][0]

        for leaked in ("password", "is_superuser", "is_staff", "user_permissions", "groups"):
            assert leaked not in row, f"API 泄露了 {leaked}"

    def test_ticket_creator_is_readonly(self, api, world):
        """creator / department 由服务端快照，客户端提交也伪造不了。"""
        token = get_token(api, "cs_staff").json()["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = api.post(
            "/api/v1/tickets/",
            {
                "title": "API 建的单",
                "priority": 2,
                "status": "open",
                "creator": world["superadmin"].pk,  # ← 伪造尝试
                "department": world["tech"].pk,
            },
            format="json",
        )

        assert resp.status_code == 201
        ticket = Ticket.objects.get(title="API 建的单")
        assert ticket.creator == world["cs_staff"]
        assert ticket.department == world["cs1"]


@pytest.mark.django_db
class TestCoexistence:
    def test_web_pages_still_work(self, client, world):
        """API 与 Web 并存，互不影响。"""
        client.force_login(world["cs_staff"])
        assert client.get(reverse("tickets:list")).status_code == 200


# --------------------------------------------------------------------------- #
# v1.1.0 刻意留下的漏洞，已在 v1.2.0 补上
#
# 那三条断言（no_role 能删任意工单 / 所有人都看到 80 张 / 任何人都能列出
# 用户和角色）现在全部翻转，见 tests/api/test_api_permissions.py 的
# TestHolesFromV110AreClosed。
#
# 想看漏洞长什么样：
#     git show v1.1.0:tests/api/test_auth.py | tail -40
# --------------------------------------------------------------------------- #
