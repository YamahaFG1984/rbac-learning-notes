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

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
# django.urls.reverse 是「URL name -> 路径」的纯函数，不依赖 request/response，
# 且 Web 层与 API 层都需要它。它在 ADR-013 的允许清单内——
# 被禁的是 django.http / shortcuts / views / rest_framework 这些
# 「响应怎么发」的东西，见 tests/rbac/test_services.py::TestKernelPurity。
from django.urls import NoReverseMatch, reverse

from .cache import TTL, bump_version, get_version, perms_key, role_depts_key, roles_key
from .signals import role_permissions_changed, user_roles_changed
from .constants import DataScope, PermType
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
# 角色展开（RBAC1）
# --------------------------------------------------------------------------- #


def _get_role_map() -> dict[int, Role]:
    """全部激活角色的 {id: Role} 映射。

    角色数量很少（几十个），一次性加载后 expand_roles 变成纯内存操作，
    向上遍历继承链不再产生查询。
    """
    data = cache.get(roles_key())
    if data is None:
        data = {r.id: r for r in Role.objects.filter(is_active=True)}
        cache.set(roles_key(), data, TTL)
    return data


def expand_roles(roles: Iterable[Role]) -> set[Role]:
    """把直接角色集合展开为「直接角色 + 全部祖先角色」。

    单继承使得这只是一次向上遍历。语义固定为 child ⊇ parent：
    拥有「客服主管」就自动拥有它 inherits_from 的「客服专员」的全部权限。

    result 集合同时起两个作用（纵深防御）：
      · 防环 —— 即使数据库里因为某种原因存在了环（比如绕过 clean() 直接
        update()），展开也不会死循环。clean() 防止环被存进去，这里防止
        已存在的环导致死循环，两道独立的防线。
      · 去重剪枝 —— 多个角色共享同一祖先时，祖先只展开一次。
    """
    role_map = _get_role_map()
    result: set[Role] = set()
    seen_ids: set[int] = set()
    for role in roles:
        if role.pk in seen_ids or not role.is_active:
            continue
        result.add(role)
        seen_ids.add(role.pk)
        current_id = role.inherits_from_id
        depth = 0
        while current_id is not None and depth < settings.RBAC_MAX_ROLE_DEPTH:
            if current_id in seen_ids:
                break  # 剪枝：这条链上面都展开过了
            ancestor = role_map.get(current_id)  # 内存查找，不查库
            if ancestor is None:
                break  # 已停用的祖先不在 map 里
            result.add(ancestor)
            seen_ids.add(current_id)
            current_id = ancestor.inherits_from_id
            depth += 1
    return result


def get_role_effective_codes(role) -> frozenset[str]:
    """单个角色展开继承后的全部权限码。"""
    return frozenset(
        Permission.objects.filter(
            role_permissions__role__in=expand_roles([role]),
            is_active=True,
            is_deprecated=False,
        )
        .exclude(code__isnull=True)
        .exclude(code="")
        .values_list("code", flat=True)
        .distinct()
    )


def get_role_perm_sources(role) -> dict[str, Role]:
    """权限码 -> 授予它的角色。用于回答「这个权限从哪来的」。

    单继承的可解释性优势就体现在这里：答案永远是一条链，不是一张图。
    从最远的祖先开始往回填，直接授予的会覆盖继承来的，
    显示时优先展示「最近的来源」。
    """
    chain = []
    current, depth = role, 0
    while current is not None and depth <= settings.RBAC_MAX_ROLE_DEPTH:
        chain.append(current)
        current = current.inherits_from
        depth += 1

    sources: dict[str, Role] = {}
    for ancestor in reversed(chain):  # 祖先 -> 自身
        codes = (
            Permission.objects.filter(
                role_permissions__role=ancestor, is_active=True, is_deprecated=False
            )
            .exclude(code__isnull=True)
            .values_list("code", flat=True)
        )
        for code in codes:
            sources[code] = ancestor
    return sources


# --------------------------------------------------------------------------- #
# 权限解析
# --------------------------------------------------------------------------- #


def get_user_perm_codes(user) -> frozenset[str]:
    """解析用户的有效权限码集合。

    v0.12.0 起含角色继承，v0.16.0 起含两级缓存。

    注意缓存是**包在原有逻辑外面**的——_resolve_perm_codes() 就是
    v0.12.0 的函数体，一行没改。好的抽象让优化可以后加。
    """
    if not user or not user.is_authenticated or not user.is_active:
        return frozenset()

    if user.is_superuser:
        return ALL_PERMS  # 短路，连缓存路径都不进

    # L1 请求级：挂在 user 对象上而不是 request 上——services 不认识 request
    # （ADR-013），挂 user 上 Web 层和 API 层都能用。
    #
    # ⚠️ L1 必须带版本校验。bump_version() 只让 L2 的 key 不可达，
    #    动不了已经挂在 user 对象上的属性。同一个请求里先改权限再读权限
    #    （或测试里复用同一个 user 对象）就会读到过期值。
    #    代价是每次多一次 cache.get(版本号)——相比 50 次重复的 DB 解析，
    #    这个代价可以忽略。
    version = get_version()
    cached = getattr(user, "_rbac_perm_cache", None)
    if cached is not None and cached[0] == version:
        return cached[1]

    # L2 进程外
    key = perms_key(user.pk)
    codes = cache.get(key)
    if codes is None:
        codes = _resolve_perm_codes(user)
        cache.set(key, codes, TTL)

    try:
        user._rbac_perm_cache = (version, codes)
    except AttributeError:  # AnonymousUser 等不可写属性的对象
        pass
    return codes


def _resolve_perm_codes(user) -> frozenset[str]:
    """真正查库的部分。v0.12.0 的函数体原样搬进来，一行没改。"""
    direct_roles = Role.objects.filter(user_roles__user=user, is_active=True)
    all_roles = expand_roles(direct_roles)  # ← RBAC0 -> RBAC1 的全部改动
    if not all_roles:
        return frozenset()

    return frozenset(
        Permission.objects.filter(
            role_permissions__role__in=all_roles,
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


def _role_direct_codes(role) -> set[str]:
    return set(
        Permission.objects.filter(role_permissions__role=role)
        .exclude(code__isnull=True)
        .values_list("code", flat=True)
    )


@transaction.atomic
def save_role_permissions(role, permission_ids, actor=None):
    """全量覆盖式保存角色的直接权限。

    必须在事务里：不加事务的话，删完之后 bulk_create 抛异常，
    这个角色的权限就全没了，而且没人会立刻发现。

    ⚠️ v0.17.0 新增：删除**之前**先读一次旧集合，用于审计日志的前后快照。

       回顾 v0.5.0 陷阱 2 —— 当时我说「先删后插现在够用，但心里有数
       这是一处已知会被改的地方」。现在就是那个时候，而改动成本只是
       多读一次旧集合。**这就是「什么时候该提前设计、什么时候该等」
       的实际答案：等到现在再改，成本很小，所以当初等是对的。**
    """
    old_codes = _role_direct_codes(role)
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
    # ⚠️ bulk_create **不触发** post_save 信号——光挂 signals.py 是不够的。
    #    （queryset.delete() 会触发 post_delete，但 bulk_create/bulk_update 不会。）
    #    这里必须显式 bump 一次，否则改完权限缓存不失效。
    bump_version()

    new_codes = _role_direct_codes(role)
    role_permissions_changed.send(
        sender=None,
        role=role,
        actor=actor,
        before=sorted(old_codes),
        after=sorted(new_codes),
        added=sorted(new_codes - old_codes),
        removed=sorted(old_codes - new_codes),
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

    old_ids = set(UserRole.objects.filter(user=user).values_list("role_id", flat=True))

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
    # ⚠️ bulk_create **不触发** post_save 信号。
    bump_version()
    user_roles_changed.send(
        sender=None,
        user=user,
        actor=granted_by,
        before=sorted(old_ids),
        after=sorted(valid_ids),
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


# --------------------------------------------------------------------------- #
# 数据权限（ADR-007）
#
# 功能权限和数据权限的实现机制根本不同，必须彻底分离：
#
#                功能权限            数据权限
#   回答          能不能执行          能对哪些行执行
#   结果          布尔值              集合（SQL 的 WHERE 条件）
#   位置          视图层装饰器        Manager 层
#   绕过的后果    垂直越权            水平越权
#
# 试图用一套机制表达两者，是权限系统腐化的头号原因。
# --------------------------------------------------------------------------- #


def get_user_dept_ids(user, include_children: bool = True) -> set[int]:
    """当前用户的部门 ID 集合。

    返回**集合**而非单值——现在用户只有一个部门（FR-1.4 的简化），
    返回单元素集合看起来很傻，但这是刻意的：将来支持兼岗（一人多部门）时，
    只需改这一个函数，所有调用方都不用动。

    注意分寸：我们**预留了形状，但没有预先实现**。预留形状的成本是 0
    （就是个返回类型的选择），预先实现兼岗的成本是一整套模型改造。
    """
    from apps.accounts.models import Department

    dept = getattr(user, "department", None)
    # 默认拒绝 4：用户无部门 -> 空集，不是全集。
    # 写成返回全部部门的话，无部门用户会绕过所有部门限制。
    if dept is None:
        return set()
    if not include_children:
        return {dept.id}
    return set(
        Department.objects.filter(path__startswith=dept.path, is_active=True).values_list(
            "id", flat=True
        )
    )


def get_role_custom_dept_ids(role) -> set[int]:
    """角色自定义数据范围的部门 ID 集合，**含各部门的子树**。

    为什么含子树？管理员勾选「客服部」时，他的意图几乎肯定是
    「客服部及其下属」——只含本级的话，勾 3 个子部门要点 4 次，
    而且新增子部门后还要记得回来补勾。

    2 次查询，与勾选的部门数量无关。
    """
    from functools import reduce
    import operator

    from apps.accounts.models import Department

    cached = cache.get(role_depts_key(role.pk))
    if cached is not None:
        return cached

    paths = list(
        Department.objects.filter(role_departments__role=role, is_active=True).values_list(
            "path", flat=True
        )
    )
    if not paths:
        # 选了 CUSTOM 却一个部门都没勾 -> 空集，不是全集
        cache.set(role_depts_key(role.pk), set(), TTL)
        return set()
    condition = reduce(operator.or_, (Q(path__startswith=p) for p in paths))
    result = set(
        Department.objects.filter(condition, is_active=True).values_list("id", flat=True)
    )
    cache.set(role_depts_key(role.pk), result, TTL)
    return result


@transaction.atomic
def save_role_departments(role, department_ids):
    """保存角色的自定义部门范围。

    ⚠️ 后端不能信任前端的显隐控制：用户选了 SELF_ONLY 却提交了一堆部门 ID
       时必须忽略，否则一旦有人把 scope 改成 CUSTOM，就会出现意外的范围。
    """
    from apps.accounts.models import Department

    from .models import RoleDepartment

    RoleDepartment.objects.filter(role=role).delete()
    if role.data_scope != DataScope.CUSTOM:
        bump_version()
        return set()

    valid_ids = set(
        Department.objects.filter(id__in=department_ids, is_active=True).values_list(
            "id", flat=True
        )
    )
    RoleDepartment.objects.bulk_create(
        [RoleDepartment(role=role, department_id=d) for d in sorted(valid_ids)]
    )
    # ⚠️ bulk_create **不触发** post_save 信号——光挂 signals.py 是不够的。
    #    （queryset.delete() 会触发 post_delete，但 bulk_create/bulk_update 不会。）
    #    这里必须显式 bump 一次，否则改完权限缓存不失效。
    bump_version()
    return valid_ids


def get_role_department_ids(role):
    """角色**直接勾选**的部门 ID（不含子树），用于表单回显。"""
    from .models import RoleDepartment

    return set(
        RoleDepartment.objects.filter(role=role).values_list("department_id", flat=True)
    )


def build_scope_q(user, cfg) -> Q | None:
    """构造数据范围过滤条件。

    返回 None       表示「不过滤」（全部数据）
    返回 Q(pk__in=[]) 表示「空集」（默认拒绝）

    ⚠️ 本函数有**四处默认拒绝**，每一处写反都是严重越权：

        Q()          空条件   -> 不过滤 -> 返回全集   ❌
        Q(pk__in=[]) 不可满足 -> 返回空集             ✅

    差两个字符，安全后果天差地别。这四个分支在正常使用中永远不会被触发，
    所以**只有测试能保证它们是对的**。

    cfg.owner_field: 归属人字段名，如 "creator"
    cfg.dept_field:  归属部门字段名，如 "department"
    """
    # 默认拒绝 1：未登录 / 已禁用
    if not user or not user.is_authenticated or not user.is_active:
        return Q(pk__in=[])

    if user.is_superuser:
        return None  # 短路，在任何查询之前

    roles = expand_roles(Role.objects.filter(user_roles__user=user, is_active=True))

    # 默认拒绝 2：无任何角色。
    # 这是最常见的状态（新建用户还没配角色），也是后果最严重的：
    # 写成 Q() 就是「新用户默认看到全公司数据」。
    if not roles:
        return Q(pk__in=[])

    owner_field, dept_field = cfg.owner_field, cfg.dept_field
    q = Q()
    matched = False

    for role in roles:
        scope = role.data_scope

        if scope == DataScope.ALL:
            return None  # 短路：最宽范围，无需再算

        if scope == DataScope.DEPT_AND_BELOW:
            sub = Q(**{f"{dept_field}_id__in": get_user_dept_ids(user, True)})
        elif scope == DataScope.DEPT_ONLY:
            sub = Q(**{f"{dept_field}_id__in": get_user_dept_ids(user, False)})
        elif scope == DataScope.SELF_ONLY:
            sub = Q(**{f"{owner_field}_id": user.pk})
        elif scope == DataScope.CUSTOM:
            sub = Q(**{f"{dept_field}_id__in": get_role_custom_dept_ids(role)})
        else:
            continue  # 枚举脏数据，跳过

        # ⚠️ 真并集，不是「取最宽枚举」。
        #
        # 角色A=SELF_ONLY(4)、角色B=CUSTOM(5) 时，按编号取最宽会得到
        # SELF_ONLY——丢掉了角色B授予的市场部数据。但 RBAC 的基本语义
        # 就是「多角色权限取并集」，数据范围是权限的一部分，
        # 没有理由用不同的合并规则。
        q |= sub
        matched = True

    # 默认拒绝 3：所有角色的 scope 都不可识别（枚举脏数据）
    if not matched:
        return Q(pk__in=[])

    # ABAC 扩展点：业务模型可定义 extra_q(user) 返回附加条件。
    # 这是通往 ABAC 的门，但我们只开一条缝——开太大就重新发明了策略引擎。
    extra = getattr(cfg, "extra_q", None)
    if extra:
        q &= extra(user)
    return q
