"""订阅 rbac 发出的信号。

依赖方向：audit -> rbac ✅（rbac 不认识 audit）
"""

from django.dispatch import receiver

from apps.rbac.signals import (
    permission_denied,
    role_permissions_changed,
    role_scope_changed,
    user_roles_changed,
)

from .constants import AuditAction, AuditResult
from .services import log


@receiver(permission_denied)
def on_permission_denied(sender, user, path, method, required_perm, ip, user_agent, **kwargs):
    log(
        AuditAction.PERM_DENIED,
        actor=user,
        detail={"path": path, "method": method, "required_perm": required_perm},
        ip=ip,
        user_agent=user_agent,
        result=AuditResult.FAILURE,
    )


@receiver(role_permissions_changed)
def on_role_permissions_changed(sender, role, actor, before, after, added, removed, **kwargs):
    """⚠️ 记录**变更前后**，不只是「改过」。

    「张三 在 3月5日 修改了 客服主管 的权限」——改成什么了？
    三个月后这条日志毫无价值。审计日志要能回答的是
    「当时到底发生了什么」，不是「有人动过」。
    """
    log(
        AuditAction.ROLE_PERM_SET,
        actor=actor,
        target=role,
        detail={"before": before, "after": after, "added": added, "removed": removed},
    )


@receiver(user_roles_changed)
def on_user_roles_changed(sender, user, actor, before, after, **kwargs):
    log(
        AuditAction.USER_ROLE_SET,
        actor=actor,
        target=user,
        detail={
            "before": before,
            "after": after,
            "added": sorted(set(after) - set(before)),
            "removed": sorted(set(before) - set(after)),
        },
    )


@receiver(role_scope_changed)
def on_role_scope_changed(sender, role, actor, before, after, **kwargs):
    """📌 数据范围变更（v1.3.0 补）。

    这个 receiver 之前不存在，AuditAction.ROLE_SCOPE_SET 是个
    「定义了却没人发出」的枚举值——把角色从「仅本人」改成「全部数据」
    不留任何痕迹，而这是影响最大的权限变更之一（FR-9.2 是 P0）。

    「需求写了但没落地」最难发现的形态就是这种：不报错、不缺功能，
    只是那条日志永远不会出现。**枚举值和它的发出点应该成对存在。**
    """
    log(
        AuditAction.ROLE_SCOPE_SET,
        actor=actor,
        target=role,
        detail={"before": before, "after": after},
    )
