"""权限缓存与失效（ADR-010）。

失效难题：管理员改了「客服专员」角色的权限，需要失效谁的缓存？
  · 所有直接拥有该角色的用户
  · 所有拥有「客服主管」的用户（因为主管继承自专员）
  · 所有拥有任何**间接**继承该角色的角色的用户

逐 key 删除要先反查出这批用户——一次可能涉及数千用户的查询，
而且这个反查逻辑本身就容易写漏（尤其是继承链那部分）。

我们用**全局版本号**：key 里带版本号，任何权限相关变更就 incr 一次，
所有旧 key 立即不可达，靠 TTL 自然淘汰。

    失效漏了 -> 「权限已撤销但仍生效」 -> 安全问题
    失效多了 -> 缓存命中率短暂下降     -> 性能问题

用**可量化的性能损失**换**不可量化的正确性保证**。
在安全相关的设计里，这个方向的交换几乎总是对的；反过来几乎总是错的。

代价可量化：企业后台的权限变更是低频操作（一天几次到几十次），
用户数千级。一次全量失效的后果是接下来几分钟缓存命中率下降。
"""

from django.conf import settings
from django.core.cache import cache
from django.db import models

VERSION_KEY = getattr(settings, "RBAC_VERSION_KEY", "rbac:version")
TTL = getattr(settings, "RBAC_CACHE_TTL", 1800)


def get_version() -> int:
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.set(VERSION_KEY, 1, None)  # None = 永不过期
        return 1
    return version


def bump_version() -> None:
    """任何权限相关变更后调用。"""
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # key 不存在
        cache.set(VERSION_KEY, 1, None)


def perms_key(user_id: int) -> str:
    return f"rbac:perms:{user_id}:{get_version()}"


def roles_key() -> str:
    return f"rbac:roles:all:{get_version()}"


def role_depts_key(role_id: int) -> str:
    return f"rbac:role_depts:{role_id}:{get_version()}"


class RbacQuerySet(models.QuerySet):
    """会自动失效缓存的 QuerySet。

    ⚠️ Django 的信号覆盖不全，这是加缓存时最容易踩的坑：

        obj.save() / obj.delete()      -> 触发 post_save / post_delete  ✅
        queryset.delete()              -> 逐个触发 post_delete          ✅
        queryset.update()              -> **不触发**                    ❌
        bulk_create() / bulk_update()  -> **不触发**                    ❌

    而 `.update()` 是极常见的写法。要求每个调用点都记得手动 bump_version()
    就回到了「靠自觉」——那正是我们要避免的。

    所以在 QuerySet 层拦住 update/delete，让机制覆盖常见路径。
    bulk_create 走的是 Manager 不是 QuerySet，仍需在业务函数里显式 bump
    （已在 services.save_* 里做了），这一点在注释里标明。
    """

    def update(self, **kwargs):
        result = super().update(**kwargs)
        bump_version()
        return result

    def delete(self):
        result = super().delete()
        bump_version()
        return result
