from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role, RolePermission
from apps.rbac.services import get_role_permission_ids, save_role_permissions


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)
    return Permission.objects.exclude(code__isnull=True)


@pytest.mark.django_db
class TestRoleModel:
    def test_default_data_scope_is_narrowest(self):
        """默认值必须指向「出错时后果最轻」的方向。

        忘配数据范围 -> 看得太少（有人报障）而不是看得太多（没人报障）。
        """
        role = Role.objects.create(code="r1", name="角色1")
        assert role.data_scope == DataScope.SELF_ONLY
        assert role.data_scope != DataScope.ALL

    def test_scope_codes_ordered_wide_to_narrow(self):
        """编号从大范围到小范围递增，min() 即最宽。"""
        assert DataScope.ALL < DataScope.DEPT_AND_BELOW < DataScope.DEPT_ONLY
        assert DataScope.DEPT_ONLY < DataScope.SELF_ONLY < DataScope.CUSTOM

    def test_builtin_role_cannot_be_deleted(self):
        role = Role.objects.create(code="builtin", name="内置", is_builtin=True)
        with pytest.raises(RuntimeError, match="不可删除"):
            role.delete()
        assert Role.objects.filter(pk=role.pk).exists()

    def test_normal_role_can_be_deleted(self):
        role = Role.objects.create(code="normal", name="普通")
        role.delete()
        assert not Role.objects.filter(pk=role.pk).exists()


@pytest.mark.django_db
class TestSaveRolePermissions:
    def test_roundtrip(self, perms):
        role = Role.objects.create(code="r", name="角色")
        ids = list(perms.values_list("id", flat=True))[:3]

        save_role_permissions(role, ids)

        assert get_role_permission_ids(role) == set(ids)

    def test_overwrite_replaces_not_appends(self, perms):
        role = Role.objects.create(code="r", name="角色")
        all_ids = list(perms.values_list("id", flat=True))

        save_role_permissions(role, all_ids[:3])
        save_role_permissions(role, all_ids[3:5])

        assert get_role_permission_ids(role) == set(all_ids[3:5])

    def test_rejects_unknown_permission_ids(self, perms):
        """永远不要信任客户端提交的主键。"""
        role = Role.objects.create(code="r", name="角色")
        valid = list(perms.values_list("id", flat=True))[:1]

        save_role_permissions(role, valid + [999999])

        assert get_role_permission_ids(role) == set(valid)

    def test_rejects_deprecated_permissions(self, perms):
        role = Role.objects.create(code="r", name="角色")
        target = perms.first()
        Permission.objects.filter(pk=target.pk).update(is_deprecated=True)

        save_role_permissions(role, [target.pk])

        assert get_role_permission_ids(role) == set()

    def test_transaction_rolls_back_on_failure(self, perms):
        """删完之后写入失败，原有权限不能丢。"""
        role = Role.objects.create(code="r", name="角色")
        ids = list(perms.values_list("id", flat=True))[:3]
        save_role_permissions(role, ids)

        with patch.object(
            RolePermission.objects, "bulk_create", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                save_role_permissions(role, ids[:1])

        assert get_role_permission_ids(role) == set(ids)

    def test_unique_together_enforced(self, perms):
        role = Role.objects.create(code="r", name="角色")
        perm = perms.first()
        RolePermission.objects.create(role=role, permission=perm)
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                RolePermission.objects.create(role=role, permission=perm)


@pytest.fixture
def admin_client_su(client, django_user_model, perms):
    """v0.9.0 起视图受权限保护，这些页面需要一个能进去的账号。"""
    su = django_user_model.objects.create_superuser(username="su", password="x")
    client.force_login(su)
    return client


@pytest.mark.django_db
class TestRoleViews:
    def test_perm_assign_page_query_count(
        self, admin_client_su, perms, django_assert_num_queries
    ):
        role = Role.objects.create(code="r", name="角色")
        # 9 = 认证 2（session 读 + user 读，AuthenticationMiddleware）
        #   + 业务 3（get_object_or_404(Role) + 已勾选 ID + 权限树全量）
        #   + 侧边栏菜单 1（v0.11.0 起动态渲染，一次取全部菜单节点）
        #   + session 回写 3（SAVEPOINT / UPDATE django_session / RELEASE）
        #
        # 最后那 3 次是 SESSION_SAVE_EVERY_REQUEST=True 的代价——滑动过期
        # 意味着**每个请求**都写一次 session 存储（v0.7.0 记过这笔账，这里实测到了）。
        # 生产环境把 session 换成 Redis 就没有这 3 次数据库写。
        #
        # 关键：业务那 3 次与树的深度和节点数无关，菜单那 1 次与层级无关。
        # 递归查库的实现会变成 O(节点数)。超管走 ALL_PERMS 短路，鉴权本身不产生查询。
        with django_assert_num_queries(9):
            resp = admin_client_su.get(reverse("rbac:role_perm_assign", args=[role.pk]))
        assert resp.status_code == 200

    def test_perm_assign_post_saves(self, admin_client_su, perms):
        role = Role.objects.create(code="r", name="角色")
        ids = [str(i) for i in perms.values_list("id", flat=True)[:2]]

        resp = admin_client_su.post(
            reverse("rbac:role_perm_assign", args=[role.pk]), {"permissions": ids}
        )

        assert resp.status_code == 302
        assert get_role_permission_ids(role) == {int(i) for i in ids}

    def test_anonymous_cannot_reach_perm_assign(self, client, perms):
        """v0.9.0 的鉴权确实生效了。"""
        role = Role.objects.create(code="r", name="角色")
        resp = client.get(reverse("rbac:role_perm_assign", args=[role.pk]))
        assert resp.status_code == 302  # 跳登录页

    def test_form_excludes_is_builtin(self):
        """is_builtin 不能从界面改——白名单 fields 而非黑名单 exclude。"""
        from apps.rbac.forms import RoleForm

        assert "is_builtin" not in RoleForm().fields
