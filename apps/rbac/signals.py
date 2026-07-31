"""权限变更 -> 缓存失效。

用信号挂载，不在视图里手写调用 bump_version()。

信号在这里是恰当的用法：它天然是横切关注点，且不能被遗漏——
shell、管理命令、admin、测试，任何路径改了数据都会触发。

（对比 ADR-009 里我们**反对**用 thread-local 做隐式过滤。同样是隐式机制，
 差别在于：信号的作用是「让某件事一定发生」，thread-local 的作用是
 「改变查询的语义」。前者失败导致性能问题，后者失败导致安全问题；
 前者的行为在任何上下文都一致，后者依赖上下文。
 隐式机制用于「保证副作用发生」是好的，用于「决定业务语义」是危险的。）
"""

import django.dispatch
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_version
from .models import Permission, Role, RoleDepartment, RolePermission, UserRole


@receiver(post_save, sender=RolePermission)
@receiver(post_delete, sender=RolePermission)
@receiver(post_save, sender=UserRole)
@receiver(post_delete, sender=UserRole)
@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
@receiver(post_save, sender=RoleDepartment)
@receiver(post_delete, sender=RoleDepartment)
@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
def invalidate_rbac_cache(sender, **kwargs):
    bump_version()


# --------------------------------------------------------------------------- #
# 反转依赖：rbac 不能 import audit（CLAUDE.md 的依赖方向是 audit -> rbac）。
#
# rbac 定义并发送这个信号，audit 订阅它。这样「记录被拒绝的访问」这件事
# 就不需要 rbac 知道 audit 的存在。
#
# 信号在这里的作用是**反转依赖方向**——这是它的另一个恰当用法
# （前一个是「保证副作用一定发生」，见本文件顶部的缓存失效）。
# --------------------------------------------------------------------------- #

permission_denied = django.dispatch.Signal()

role_permissions_changed = django.dispatch.Signal()
user_roles_changed = django.dispatch.Signal()
