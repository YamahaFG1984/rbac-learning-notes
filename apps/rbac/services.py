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
# django.urls.reverse 是「URL name -> 路径」的纯函数，不依赖 request/response，
# 且 Web 层与 API 层都需要它。它在 ADR-013 的允许清单内——
# 被禁的是 django.http / shortcuts / views / rest_framework 这些
# 「响应怎么发」的东西，见 tests/rbac/test_services.py::TestKernelPurity。
from django.urls import NoReverseMatch, reverse

from .constants import PermType
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


# --------------------------------------------------------------------------- #
# 菜单树
# --------------------------------------------------------------------------- #


def get_user_menu_tree(user) -> list[dict]:
    """构建当前用户可见的菜单树。

    算法方向是**自底向上**：先标记有权限的 menu 节点，再沿 parent 链向上
    保留全部祖先目录。

    为什么不能自顶向下？因为 catalog 没有权限码，判断不了它自己。
    目录的可见性 = 它是否有任何一个有权限的后代菜单。
    自底向上的副作用正好是我们要的：空目录（无任何有权限的后代）
    自然不会被保留——一个点开是空的目录，用户会以为系统坏了。

    查询次数固定为 1（不含权限解析），与菜单层级无关（NFR-3）。

    返回 list[dict] 而不是 model 实例：v1.2.0 的 /auth/profile 要把它
    直接 JSON 序列化给前端。
    """
    codes = get_user_perm_codes(user)

    nodes = list(
        Permission.objects.filter(
            perm_type__in=[PermType.CATALOG, PermType.MENU],
            is_active=True,
            is_visible=True,
            is_deprecated=False,
        )
    )
    by_id = {n.id: n for n in nodes}

    # 第一步：标记有权限的 menu
    keep = {
        n.id for n in nodes if n.perm_type == PermType.MENU and n.code and n.code in codes
    }

    # 第二步：向上保留祖先目录
    for node_id in list(keep):
        parent_id = by_id[node_id].parent_id
        while parent_id is not None and parent_id not in keep:
            keep.add(parent_id)  # 碰到已保留的祖先就停——再往上都保留过了
            parent_id = by_id[parent_id].parent_id if parent_id in by_id else None

    def safe_reverse(url_name):
        """url_name 是人手写在 permissions.py 里的字符串，可能写错，
        也可能对应的 URL 后来被删了。不处理的话，一个写错的 url_name
        会让整个侧边栏渲染崩溃——所有页面都打不开。"""
        if not url_name:
            return None
        try:
            return reverse(url_name)
        except NoReverseMatch:
            return None

    children_of = {}
    for node in nodes:
        if node.id in keep:
            children_of.setdefault(node.parent_id, []).append(node)
    for siblings in children_of.values():
        # 同级按 order_num 排——不能靠 ORDER BY path，那是字符串排序
        siblings.sort(key=lambda n: (n.order_num, n.pk))

    def assemble(parent_id):
        return [
            {
                "id": n.id,
                "name": n.name,
                "icon": n.icon,
                "url": safe_reverse(n.url_name),
                "perm_type": n.perm_type,
                "children": assemble(n.id),
            }
            for n in children_of.get(parent_id, [])
        ]

    return assemble(None)
