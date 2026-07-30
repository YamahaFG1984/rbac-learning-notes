"""RBAC 权限内核。

⚠️ 本模块是纯函数模块，严禁 import django.http / DRF 的任何东西，
   函数也不接收 request 参数。详见 ADR-013。

   它同时服务于 Web 模板层和（v1.1.0 起的）API 层：
   「不通过之后做什么」是表现层的事，内核只回答「通过还是不通过」。

   这条约束的收益延迟到 v1.2.0 一次性兑现，届时的验收条件是：
       git diff v1.1.0 v1.2.0 -- apps/rbac/services.py   # 期望输出为空
"""

from django.db import transaction

from .models import Permission, RolePermission


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
