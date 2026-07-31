import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.models import AuditLog
from apps.audit.permissions import AuditPerm
from apps.audit.services import log
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import save_role_permissions, save_user_roles

PASSWORD = "demo1234!"


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
    return django_user_model.objects.create_user(username="zhangsan", password=PASSWORD)


@pytest.mark.django_db
class TestImmutability:
    def test_cannot_modify_existing(self, perms):
        entry = log(AuditAction.LOGIN, detail={"a": 1})
        entry.detail = {"a": 2}
        with pytest.raises(RuntimeError, match="不可修改"):
            entry.save()

    def test_cannot_delete_instance(self, perms):
        entry = log(AuditAction.LOGIN)
        with pytest.raises(RuntimeError, match="不可删除"):
            entry.delete()

    def test_cannot_bulk_delete(self, perms):
        """⚠️ 模型的 delete() 挡不住 queryset.delete()——那走的是 QuerySet。"""
        log(AuditAction.LOGIN)
        with pytest.raises(RuntimeError, match="不可删除"):
            AuditLog.objects.all().delete()

    def test_cannot_bulk_update(self, perms):
        log(AuditAction.LOGIN)
        with pytest.raises(RuntimeError, match="不可修改"):
            AuditLog.objects.all().update(action=AuditAction.LOGOUT)


@pytest.mark.django_db
class TestAuthLogging:
    def test_login_success(self, client, staff):
        client.post(
            reverse("accounts:login"),
            {"username": "zhangsan", "password": PASSWORD},
            REMOTE_ADDR="10.0.0.1",
            HTTP_USER_AGENT="pytest-agent",
        )
        entry = AuditLog.objects.get(action=AuditAction.LOGIN)
        assert entry.actor == staff
        assert entry.ip == "10.0.0.1"
        assert entry.user_agent == "pytest-agent"
        assert entry.result == AuditResult.SUCCESS

    def test_login_failure_records_username_without_actor(self, client, staff):
        client.post(reverse("accounts:login"), {"username": "zhangsan", "password": "bad"})
        entry = AuditLog.objects.get(action=AuditAction.LOGIN_FAILED)
        assert entry.actor is None  # 认证失败，没有可信的 actor
        assert entry.detail["username"] == "zhangsan"
        assert entry.detail["attempts"] == 1
        assert entry.result == AuditResult.FAILURE

    def test_logout(self, client, staff):
        client.force_login(staff)
        client.post(reverse("accounts:logout"))
        assert AuditLog.objects.filter(action=AuditAction.LOGOUT, actor=staff).exists()


@pytest.mark.django_db
class TestPermissionDeniedLogging:
    def test_denied_access_is_recorded(self, client, staff):
        """rbac 通过信号通知 audit——rbac 不 import audit，依赖方向保持 audit -> rbac。"""
        client.force_login(staff)
        client.get(reverse("rbac:role_list"))

        entry = AuditLog.objects.get(action=AuditAction.PERM_DENIED)
        assert entry.actor == staff
        assert entry.detail["required_perm"] == "system:role:view"
        assert entry.detail["path"] == reverse("rbac:role_list")
        assert entry.result == AuditResult.FAILURE

    def test_rbac_does_not_import_audit(self):
        """依赖方向：audit -> rbac，不能反过来（CLAUDE.md 第 3 节）。"""
        import ast
        import inspect
        from pathlib import Path

        from apps.rbac import decorators, services, signals

        for module in (decorators, services, signals):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    assert not m.startswith("apps.audit"), (
                        f"{module.__name__} 不该依赖 apps.audit——依赖方向是 audit -> rbac"
                    )


@pytest.mark.django_db
class TestChangeSnapshots:
    def test_role_permission_change_records_before_and_after(self, staff, perms):
        """⚠️ 只记「改过」的日志三个月后毫无价值。

        审计日志要能回答「当时到底发生了什么」，不是「有人动过」。
        """
        role = Role.objects.create(code="r", name="角色")
        view = Permission.objects.get(code="system:dept:view")
        create = Permission.objects.get(code="system:dept:create")

        save_role_permissions(role, [view.pk], actor=staff)
        save_role_permissions(role, [create.pk], actor=staff)

        entry = AuditLog.objects.filter(action=AuditAction.ROLE_PERM_SET).first()
        assert entry.detail["before"] == ["system:dept:view"]
        assert entry.detail["after"] == ["system:dept:create"]
        assert entry.detail["added"] == ["system:dept:create"]
        assert entry.detail["removed"] == ["system:dept:view"]
        assert entry.target_repr == "角色"

    def test_user_role_change_records_diff(self, staff, perms, django_user_model):
        admin = django_user_model.objects.create_user(username="admin", password="x")
        a = Role.objects.create(code="a", name="a")
        b = Role.objects.create(code="b", name="b")

        save_user_roles(staff, [a.pk], granted_by=admin)
        save_user_roles(staff, [b.pk], granted_by=admin)

        entry = AuditLog.objects.filter(action=AuditAction.USER_ROLE_SET).first()
        assert entry.detail["added"] == [b.pk]
        assert entry.detail["removed"] == [a.pk]
        assert entry.actor == admin


@pytest.mark.django_db
class TestActorSnapshot:
    def test_actor_name_survives_user_deletion(self, staff, perms):
        """actor 是 SET_NULL——不冗余存用户名的话，用户一删就不知道是谁操作的了。"""
        log(AuditAction.LOGIN, actor=staff)
        entry = AuditLog.objects.first()
        assert entry.actor_name == "zhangsan"

        staff.delete()

        entry.refresh_from_db()
        assert entry.actor is None
        assert entry.actor_name == "zhangsan"  # 快照还在


@pytest.mark.django_db
class TestResilience:
    def test_write_failure_does_not_break_caller(self, perms, monkeypatch):
        """审计写失败不该让用户的正常操作挂掉。"""
        from apps.audit import services

        def boom(*a, **kw):
            raise RuntimeError("db down")

        monkeypatch.setattr(services.AuditLog.objects, "create", boom)
        assert services.log(AuditAction.LOGIN) is None  # 不抛异常

    def test_non_serialisable_detail_is_caught(self, perms):
        """JSONField 放不进去的东西会炸——但不能炸到调用方。"""
        assert log(AuditAction.LOGIN, detail={"bad": {1, 2, 3}}) is None


@pytest.mark.django_db
class TestViewPermission:
    def test_requires_audit_view_perm(self, client, staff):
        client.force_login(staff)
        assert client.get(reverse("audit:log_list")).status_code == 403

        grant(staff, AuditPerm.VIEW)
        assert client.get(reverse("audit:log_list")).status_code == 200
