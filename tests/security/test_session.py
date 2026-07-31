"""会话与请求层面的防护。"""

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.rbac.models import Permission, Role, RolePermission, UserRole


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


@pytest.fixture
def staff(django_user_model, perms):
    user = django_user_model.objects.create_user(username="staff", password="demo1234!")
    role = Role.objects.create(code="r", name="r")
    RolePermission.objects.create(
        role=role, permission=Permission.objects.get(code="system:dept:view")
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
class TestDisabledUser:
    def test_existing_session_dies_on_next_request(self, client, staff, django_user_model):
        """纵深防御：三道独立的 is_active 检查
        （ModelBackend.get_user / get_user_perm_codes / build_scope_q）。
        """
        client.force_login(staff)
        assert client.get(reverse("accounts:department_list")).status_code == 200

        django_user_model.objects.filter(pk=staff.pk).update(is_active=False)

        resp = client.get(reverse("accounts:department_list"))
        assert resp.status_code == 302  # 被踢回登录页
        assert reverse("accounts:login") in resp.url

    def test_disabled_user_has_no_perms(self, staff, django_user_model):
        from apps.rbac.services import get_user_perm_codes

        django_user_model.objects.filter(pk=staff.pk).update(is_active=False)
        assert get_user_perm_codes(django_user_model.objects.get(pk=staff.pk)) == frozenset()


@pytest.mark.django_db
class TestCsrfAndMethods:
    def test_write_without_csrf_token_is_rejected(self, staff, perms):
        """enforce_csrf_checks=True 才能测到真实行为——默认的 test client 会跳过 CSRF。"""
        c = Client(enforce_csrf_checks=True)
        c.force_login(staff)
        role = Role.objects.create(code="victim", name="受害")

        resp = c.post(reverse("rbac:role_delete", args=[role.pk]))

        assert resp.status_code == 403
        assert Role.objects.filter(pk=role.pk).exists()

    @pytest.mark.parametrize(
        "url_name,args",
        [
            ("rbac:role_delete", [1]),
            ("accounts:department_delete", [1]),
            ("accounts:user_delete", [1]),
            ("accounts:logout", []),
        ],
    )
    def test_destructive_actions_reject_get(self, client, staff, url_name, args):
        """删除类操作不能用 GET——否则 <img src="/delete/1/"> 就能触发。"""
        client.force_login(staff)
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code in (403, 405), f"{url_name} 接受了 GET"

    def test_no_destructive_links_in_templates(self):
        """模板里不该有指向删除类 URL 的 <a href>。"""
        import re
        from pathlib import Path

        from django.conf import settings

        pattern = re.compile(r'<a\s[^>]*href="\{%\s*url\s+\'[^\']*delete[^\']*\'')
        offenders = []
        for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.name))
        assert not offenders, f"这些模板用 <a href> 指向了删除操作：{offenders}"


@pytest.mark.django_db
class TestProdSecurityHeaders:
    def test_prod_settings_enable_hardening(self):
        import os
        from importlib import import_module

        os.environ.setdefault("DJANGO_SECRET_KEY", "test-only")
        os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "example.com")
        prod = import_module("config.settings.prod")

        assert prod.DEBUG is False
        assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert prod.X_FRAME_OPTIONS == "DENY"
        assert prod.SECURE_HSTS_SECONDS > 0
        assert prod.SESSION_COOKIE_HTTPONLY is True
        assert prod.SESSION_COOKIE_SECURE is True
        assert prod.CSRF_COOKIE_SECURE is True

    def test_prod_requires_secret_key_from_env(self):
        """缺配置就启动失败，好过带着默认密钥跑起来。"""
        import inspect
        from importlib import import_module

        source = inspect.getsource(import_module("config.settings.prod"))
        assert 'os.environ["DJANGO_SECRET_KEY"]' in source
        assert 'os.environ.get("DJANGO_SECRET_KEY"' not in source
