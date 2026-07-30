import re

import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from apps.accounts.auth_views import LOGIN_FAILED_MESSAGE

PASSWORD = "demo1234!"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="zhangsan", password=PASSWORD, real_name="张三"
    )


def login_url():
    return reverse("accounts:login")


@pytest.mark.django_db
class TestLogin:
    def test_success(self, client, user):
        resp = client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert resp.status_code == 302
        assert client.session.get("_auth_user_id") == str(user.pk)

    def test_wrong_password_uses_generic_message(self, client, user):
        resp = client.post(login_url(), {"username": "zhangsan", "password": "wrong"})
        assert resp.status_code == 200
        assert LOGIN_FAILED_MESSAGE in resp.content.decode()

    def test_unknown_user_gives_identical_message(self, client, user):
        """FR-5.2：不区分「用户不存在」和「密码错误」。

        分开提示等于给攻击者一个用户名枚举接口——他可以批量试用户名，
        先拿到有效账号清单再针对性撞库。
        """
        wrong_pw = client.post(login_url(), {"username": "zhangsan", "password": "wrong"})
        no_user = client.post(login_url(), {"username": "nobody", "password": "wrong"})

        assert LOGIN_FAILED_MESSAGE in wrong_pw.content.decode()
        assert LOGIN_FAILED_MESSAGE in no_user.content.decode()

        # 不只是文案相同——除了回显的用户名和每次都变的 CSRF token，
        # 两条路径的响应体应当逐字节无法区分。
        def normalise(resp):
            html = resp.content.decode()
            html = re.sub(r'value="[A-Za-z0-9]{32,}"', 'value="CSRF"', html)
            return html.replace("nobody", "USERNAME").replace("zhangsan", "USERNAME")

        assert normalise(wrong_pw) == normalise(no_user)

    def test_inactive_user_rejected(self, client, user):
        user.is_active = False
        user.save()
        resp = client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert resp.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_records_last_login_ip(self, client, user):
        client.post(
            login_url(),
            {"username": "zhangsan", "password": PASSWORD},
            REMOTE_ADDR="10.1.2.3",
        )
        user.refresh_from_db()
        assert user.last_login_ip == "10.1.2.3"

    def test_session_key_cycles(self, client, user):
        """login() 内部调用 cycle_key()，防会话固定攻击。"""
        client.get(login_url())
        before = client.session.session_key
        client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert client.session.session_key != before


@pytest.mark.django_db
class TestLockout:
    def test_locks_after_max_attempts(self, client, user):
        for _ in range(settings.LOGIN_FAIL_MAX_ATTEMPTS):
            client.post(login_url(), {"username": "zhangsan", "password": "wrong"})

        # 第 N+1 次即使密码正确也被拒
        resp = client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert resp.status_code == 200
        assert "_auth_user_id" not in client.session
        assert "登录失败次数过多" in resp.content.decode()

    def test_success_clears_counter(self, client, user):
        for _ in range(settings.LOGIN_FAIL_MAX_ATTEMPTS - 1):
            client.post(login_url(), {"username": "zhangsan", "password": "wrong"})

        client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        client.post(reverse("accounts:logout"))

        for _ in range(settings.LOGIN_FAIL_MAX_ATTEMPTS - 1):
            client.post(login_url(), {"username": "zhangsan", "password": "wrong"})
        resp = client.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert resp.status_code == 302  # 计数已被清零，没有被锁

    def test_lockout_keyed_by_username_not_session(self, client, user):
        """换个 session 不能绕过——所以计数不能放 session 里。"""
        from django.test import Client

        for _ in range(settings.LOGIN_FAIL_MAX_ATTEMPTS):
            client.post(login_url(), {"username": "zhangsan", "password": "wrong"})

        fresh = Client()
        resp = fresh.post(login_url(), {"username": "zhangsan", "password": PASSWORD})
        assert "_auth_user_id" not in fresh.session


@pytest.mark.django_db
class TestLogout:
    def test_post_logs_out(self, client, user):
        client.force_login(user)
        resp = client.post(reverse("accounts:logout"))
        assert resp.status_code == 302
        assert "_auth_user_id" not in client.session

    def test_get_is_rejected(self, client, user):
        """Django 5.x 起登出只接受 POST。

        GET /logout/ 意味着攻击者能用 <img src="/logout/"> 强制登出任何访客。
        """
        client.force_login(user)
        resp = client.get(reverse("accounts:logout"))
        assert resp.status_code == 405
        assert "_auth_user_id" in client.session


@pytest.mark.django_db
class TestRedirect:
    def test_next_is_honoured(self, client, user):
        target = reverse("accounts:user_list")
        resp = client.post(
            login_url(), {"username": "zhangsan", "password": PASSWORD, "next": target}
        )
        assert resp.url == target

    def test_open_redirect_is_blocked(self, client, user):
        resp = client.post(
            login_url(),
            {"username": "zhangsan", "password": PASSWORD, "next": "https://evil.example"},
        )
        assert resp.url == settings.LOGIN_REDIRECT_URL
        assert "evil.example" not in resp.url

    def test_authenticated_user_skips_login_page(self, client, user):
        client.force_login(user)
        resp = client.get(login_url())
        assert resp.status_code == 302
