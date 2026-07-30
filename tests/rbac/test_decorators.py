import pytest
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.views.generic import View

from apps.rbac.checks import _unwrap, check_view_permissions
from apps.rbac.decorators import public_view, require_any_perm, require_perm
from apps.rbac.mixins import PermRequiredMixin
from apps.rbac.models import Permission, Role, RolePermission, UserRole


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


def grant(user, *codes):
    role = Role.objects.create(code=f"r{user.pk}", name="r")
    for c in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=c))
    UserRole.objects.create(user=user, role=role)
    return role


@pytest.fixture
def staff(django_user_model, perms):
    return django_user_model.objects.create_user(username="staff", password="x")


@pytest.mark.django_db
class TestRequirePerm:
    def _view(self):
        @require_perm("system:dept:view")
        def view(request):
            return HttpResponse("ok")

        return view

    def test_allows_with_perm(self, staff, rf):
        grant(staff, "system:dept:view")
        req = rf.get("/")
        req.user = staff
        assert self._view()(req).status_code == 200

    def test_denies_without_perm(self, staff, rf):
        req = rf.get("/")
        req.user = staff
        with pytest.raises(PermissionDenied):
            self._view()(req)

    def test_superuser_bypasses(self, django_user_model, perms, rf):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        req = rf.get("/")
        req.user = su
        assert self._view()(req).status_code == 200

    def test_marks_the_wrapper(self):
        assert self._view()._required_perm == "system:dept:view"

    def test_require_any_perm(self, staff, rf):
        @require_any_perm("system:dept:view", "system:role:view")
        def view(request):
            return HttpResponse("ok")

        req = rf.get("/")
        req.user = staff
        with pytest.raises(PermissionDenied):
            view(req)

        grant(staff, "system:role:view")
        assert view(req).status_code == 200


@pytest.mark.django_db
class TestPermRequiredMixin:
    def test_denies_without_perm(self, staff, rf):
        class V(PermRequiredMixin, View):
            required_perm = "system:dept:view"

            def get(self, request):
                return HttpResponse("ok")

        req = rf.get("/")
        req.user = staff
        with pytest.raises(PermissionDenied):
            V.as_view()(req)

    def test_allows_with_perm(self, staff, rf):
        grant(staff, "system:dept:view")

        class V(PermRequiredMixin, View):
            required_perm = "system:dept:view"

            def get(self, request):
                return HttpResponse("ok")

        req = rf.get("/")
        req.user = staff
        assert V.as_view()(req).status_code == 200


class TestPublicView:
    def test_reason_is_mandatory(self):
        """reason 没有默认值——安全决策必须留下依据。

        给它默认值，这个标记就退化成了纯粹的「消警告」开关。
        """
        import inspect

        sig = inspect.signature(public_view)
        assert sig.parameters["reason"].default is inspect.Parameter.empty

    def test_marks_the_view(self):
        @public_view(reason="测试用")
        def view(request):
            return HttpResponse("ok")

        assert view._is_public is True
        assert view._public_reason == "测试用"


class TestStartupCheck:
    def test_no_warnings_in_current_urlconf(self):
        """当前所有视图都已声明——这是持续有效的回归基线。"""
        assert check_view_permissions(None) == []

    def test_detects_undeclared_function_view(self, settings):
        """构造一个裸视图，断言自检能发现它。"""
        from django.urls import path

        def naked(request):
            return HttpResponse("裸奔")

        class FakeUrlConf:
            urlpatterns = [path("naked/", naked)]

        settings.ROOT_URLCONF = FakeUrlConf
        problems = check_view_permissions(None)

        assert len(problems) == 1
        assert problems[0].id == "rbac.W001"
        assert "naked" in problems[0].msg

    def test_detects_undeclared_class_view(self, settings):
        from django.urls import path

        class NakedView(View):
            def get(self, request):
                return HttpResponse("裸奔")

        class FakeUrlConf:
            urlpatterns = [path("naked/", NakedView.as_view())]

        settings.ROOT_URLCONF = FakeUrlConf
        problems = check_view_permissions(None)

        assert len(problems) == 1
        assert "NakedView" in problems[0].msg

    def test_public_view_silences_warning(self, settings):
        from django.urls import path

        @public_view(reason="就是要公开")
        def open_view(request):
            return HttpResponse("ok")

        class FakeUrlConf:
            urlpatterns = [path("open/", open_view)]

        settings.ROOT_URLCONF = FakeUrlConf
        assert check_view_permissions(None) == []

    def test_unwrap_penetrates_decorator_chain(self):
        """装饰器链可能有好几层，自检要能穿透到声明的载体。"""
        from django.contrib.auth.decorators import login_required
        from django.views.decorators.http import require_POST

        @login_required
        @require_POST
        @require_perm("system:dept:delete")
        def view(request):
            return HttpResponse("ok")

        target = _unwrap(view)
        assert getattr(target, "_required_perm", None) == "system:dept:delete"


@pytest.mark.django_db
class TestEndToEnd:
    def test_403_page_for_missing_perm(self, client, staff):
        client.force_login(staff)
        resp = client.get(reverse("rbac:role_list"))
        assert resp.status_code == 403  # 不是 500，不是静默通过

    def test_200_with_perm(self, client, staff):
        grant(staff, "system:role:view")
        client.force_login(staff)
        assert client.get(reverse("rbac:role_list")).status_code == 200

    def test_anonymous_redirected_to_login_with_next(self, client, perms):
        """login_required 必须在外层，否则匿名用户会先撞上 403。"""
        target = reverse("rbac:role_list")
        resp = client.get(target)
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert f"next={target}" in resp.url

    def test_backend_powers_has_perm(self, staff):
        """接进 user.has_perm() 让 Django admin 和第三方代码继续可用。"""
        assert staff.has_perm("system:dept:view") is False
        grant(staff, "system:dept:view")
        staff = type(staff).objects.get(pk=staff.pk)  # 清掉 Django 的权限缓存
        assert staff.has_perm("system:dept:view") is True
