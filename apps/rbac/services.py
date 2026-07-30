"""RBAC 权限内核。

⚠️ 本模块是纯函数模块，严禁 import django.http / DRF 的任何东西，
   函数也不接收 request 参数。详见 ADR-013。

   它同时服务于 Web 模板层和（v1.1.0 起的）API 层：
   「不通过之后做什么」是表现层的事（Web 渲染 403 页面 / API 返回 403 JSON），
   内核只回答「通过还是不通过」。

   这条约束的收益延迟到 v1.2.0 一次性兑现，届时的验收条件是：
       git diff v1.1.0 v1.2.0 -- apps/rbac/services.py   # 期望输出为空
"""

from typing import Iterable

from django.db import transaction

from .models import Permission, Role, RolePermission


class _AllPerms:
    """超级管理员的权限集合哨兵。

    不返回「数据库里全部权限码的集合」，有两个理由：
      1. 那要多一次查询，而超管路径本该是零成本的短路；
      2. 语义错误——超管的含义是「绕过权限检查」，不是「拥有当前库里的所有权限」。
         检查一个尚未同步入库的权限码时，超管应该通过。
    """

    __slots__ = ()

    def __contains__(self, item):
        return True

    def __iter__(self):
        # 可迭代但为空：误用 list(perms) 时不会炸，但也不会假装拥有具体的码
        return iter(())

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __repr__(self):
        return "<AllPerms>"


ALL_PERMS = _AllPerms()


# --------------------------------------------------------------------------- #
# 权限解析
# --------------------------------------------------------------------------- #


def get_user_perm_codes(user) -> frozenset[str]:
    """解析用户的有效权限码集合。

    v0.6.0 版本：不含缓存（v0.16.0）、不含角色继承（v0.12.0）。
    先让逻辑对且看得懂——缓存是优化，优化必须建立在正确之上。
    """
    if not user or not user.is_authenticated or not user.is_active:
        return frozenset()

    if user.is_superuser:
        return ALL_PERMS  # 短路，不查库

    role_ids = list(
        Role.objects.filter(user_roles__user=user, is_active=True).values_list(
            "id", flat=True
        )
    )
    if not role_ids:
        return frozenset()

    return frozenset(
        Permission.objects.filter(
            role_permissions__role_id__in=role_ids,
            is_active=True,
            is_deprecated=False,
        )
        # catalog 类型没有权限码，不参与鉴权，只用于菜单分组。
        # 漏了这两个 exclude，None 会混进权限码集合里。
        .exclude(code__isnull=True)
        .exclude(code="")
        .values_list("code", flat=True)
        .distinct()
    )


def user_has_perm(user, code: str) -> bool:
    return code in get_user_perm_codes(user)


def user_has_any_perm(user, codes: Iterable[str]) -> bool:
    granted = get_user_perm_codes(user)
    return any(c in granted for c in codes)


def user_has_all_perms(user, codes: Iterable[str]) -> bool:
    granted = get_user_perm_codes(user)
    return all(c in granted for c in codes)


# --------------------------------------------------------------------------- #
# 授权维护
# --------------------------------------------------------------------------- #


@transaction.atomic
def save_role_permissions(role, permission_ids):
    """全量覆盖式保存角色的直接权限。

    必须在事务里：不加事务的话，删完之后 bulk_create 抛异常，
    这个角色的权限就全没了，而且没人会立刻发现。
    """
    # ⚠️ 永远不要信任客户端提交的主键——直接用前端传来的 ID 建关联，
    #    等于允许构造请求把任意 ID（含已废弃的权限点）塞进来。
    valid_ids = set(
        Permission.objects.filter(
            id__in=permission_ids, is_active=True, is_deprecated=False
        ).values_list("id", flat=True)
    )
    RolePermission.objects.filter(role=role).delete()
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission_id=pid) for pid in sorted(valid_ids)]
    )
    return valid_ids


def get_role_permission_ids(role):
    """角色**直接授予**的权限点 ID 集合。"""
    return set(
        RolePermission.objects.filter(role=role).values_list("permission_id", flat=True)
    )


@transaction.atomic
def save_user_roles(user, role_ids, granted_by=None):
    """全量覆盖式保存用户的角色。"""
    from .models import UserRole

    valid_ids = set(
        Role.objects.filter(id__in=role_ids, is_active=True).values_list("id", flat=True)
    )
    UserRole.objects.filter(user=user).delete()
    UserRole.objects.bulk_create(
        [
            UserRole(user=user, role_id=rid, granted_by=granted_by)
            for rid in sorted(valid_ids)
        ]
    )
    return valid_ids


def get_user_role_ids(user):
    from .models import UserRole

    return set(UserRole.objects.filter(user=user).values_list("role_id", flat=True))
