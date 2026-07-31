import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.context_processors import LazyPermSet
from apps.rbac.models import Permission, Role, RolePermission, UserRole


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def grant(user, *codes):
    role = Role.objects.create(code=f"r{user.pk}", name="r")
    for c in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=c))
    UserRole.objects.create(user=user, role=role)


@pytest.fixture
def staff(django_user_model, perms):
    return django_user_model.objects.create_user(username="staff", password="x")


@pytest.mark.django_db
class TestLaziness:
    def test_not_resolved_until_used(self, staff, django_assert_num_queries):
        with django_assert_num_queries(0):
            perms = LazyPermSet(staff)
            repr(perms)  # 连 repr 都不该触发解析

    def test_resolves_once(self, staff, django_assert_num_queries):
        grant(staff, "system:dept:view")
        perms = LazyPermSet(staff)
        # 3 = 全量角色映射 + 用户的直接角色 + 权限码（首次，L2 未预热）
        with django_assert_num_queries(3):
            assert "system:dept:view" in perms
            # 后续 50 次判断不再查库
            for _ in range(50):
                _ = "system:dept:create" in perms

    def test_login_page_costs_nothing(self, client, perms, django_assert_num_queries):
        """未登录页面渲染时不产生权限相关查询。"""
        with django_assert_num_queries(0):
            resp = client.get(reverse("accounts:login"))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSuperuserSentinel:
    def test_is_truthy_despite_zero_length(self, django_user_model, perms):
        """超管的 ALL_PERMS 哨兵 __len__ 是 0，但它绝不是「假」。

        不实现 __bool__ 的话，模板里 {% if perms %} 会让超管走进 else 分支。
        """
        su = django_user_model.objects.create_superuser(username="su", password="x")
        p = LazyPermSet(su)
        assert "anything:at:all" in p
        assert len(p) == 0
        assert bool(p) is True


@pytest.mark.django_db
class TestTemplateRendering:
    def test_button_hidden_without_perm(self, client, staff):
        grant(staff, "system:role:view")
        client.force_login(staff)
        resp = client.get(reverse("rbac:role_list"))
        assert resp.status_code == 200
        assert "新建角色" not in resp.content.decode()

    def test_button_shown_with_perm(self, client, staff):
        grant(staff, "system:role:view", "system:role:create")
        client.force_login(staff)
        resp = client.get(reverse("rbac:role_list"))
        assert "新建角色" in resp.content.decode()

    def test_superuser_sees_all_buttons(self, client, django_user_model, perms):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        client.force_login(su)
        html = client.get(reverse("rbac:role_list")).content.decode()
        assert "新建角色" in html


@pytest.mark.django_db
class TestHiddenButtonIsNotSecurity:
    """⚠️ 本 tag 存在的真正理由。

    隐藏按钮是**体验优化**，让用户不去点一个必然失败的东西。
    真正的安全边界只有一个：服务端视图层的 @require_perm（v0.9.0）。

    攻击者不点你的按钮，他直接发请求。
    """

    def test_hidden_delete_button_still_rejects_direct_post(self, client, staff):
        role = Role.objects.create(code="victim", name="受害角色")
        grant(staff, "system:role:view")  # 只有查看权限，没有删除权限
        client.force_login(staff)

        html = client.get(reverse("rbac:role_list")).content.decode()
        assert "删除" not in html  # 按钮确实被隐藏了

        # 但攻击者不点按钮，他直接 POST
        resp = client.post(reverse("rbac:role_delete", args=[role.pk]))

        assert resp.status_code == 403
        assert Role.objects.filter(pk=role.pk).exists()  # 角色还在

    def test_every_template_guard_has_a_view_guard(self):
        """模板里有几个 `in perms`，视图层就该有几个对应的 @require_perm。

        成对出现，缺一不可——这是权限系统里最高频的真实漏洞成因。
        """
        import re
        from pathlib import Path

        from django.conf import settings

        from apps.rbac.checks import _iter_views, _unwrap

        template_codes = set()
        pattern = re.compile(r"['\"]([a-z][a-z0-9_]*:[a-z][a-z0-9_]*:[a-z][a-z0-9_]*)['\"]\s+in\s+perms")
        for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            template_codes.update(pattern.findall(path.read_text(encoding="utf-8")))

        view_codes = set()
        for _route, view in _iter_views():
            target = _unwrap(view)
            code = getattr(target, "_required_perm", None) or getattr(
                target, "required_perm", None
            )
            if code:
                view_codes.add(code)
            view_codes.update(getattr(target, "_required_any_perms", ()) or ())

        orphans = template_codes - view_codes
        assert not orphans, (
            f"这些权限码只在模板里隐藏了按钮，服务端却没有对应的 @require_perm：{sorted(orphans)}。"
            f"攻击者直接发请求就能绕过。"
        )
