"""越权矩阵 —— 可执行的权限规格说明书。

这张表同时是三样东西：

  1. **验收清单**（PRD 的 AC-6）
  2. **回归基线** —— 任何一格从 ❌ 变 ✅ 都是安全事故，CI 会立刻变红
  3. **权限规格说明书** —— 产品问「客服主管能不能删工单」，答案在这里

> 文档会过期，测试不会——因为过期的测试会变红。

对应设计文档 6.2 的表格：

        │ 超管 │ 系统管理员 │ 客服主管 │ 客服专员 │ 无角色 │ 匿名
    ────┼──────┼───────────┼─────────┼─────────┼───────┼──────
    用户列表│  ✅  │    ✅     │   ❌    │   ❌    │  ❌   │ ↪登录
    角色配置│  ✅  │    ✅     │   ❌    │   ❌    │  ❌   │ ↪登录
    工单列表│ 全部 │   全部    │ 本部门树 │  仅本人  │  空   │ ↪登录
    工单删除│  ✅  │    ❌     │   ✅    │   ❌    │  ❌   │ ↪登录
    他部门单│  ✅  │   可见    │   404   │   404   │  404  │ ↪登录
"""

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket
from tests.factories import DEMO_PASSWORD, build_demo_world

ALL_USERS = ["superadmin", "sysadmin", "cs_manager", "cs_staff", "no_role", "anonymous"]


@pytest.fixture
def world(db):
    return build_demo_world()


@pytest.fixture
def as_user(client, world):
    def _login(key):
        if key == "anonymous":
            client.logout()
        else:
            client.force_login(world[key])
        return client

    return _login


# --------------------------------------------------------------------------- #
# 功能权限矩阵
# --------------------------------------------------------------------------- #

# (用户, 路由, 方法, 期望状态码)
FUNCTIONAL_MATRIX = [
    # 用户列表
    ("superadmin", "accounts:user_list", "get", 200),
    ("sysadmin", "accounts:user_list", "get", 200),
    ("cs_manager", "accounts:user_list", "get", 403),
    ("cs_staff", "accounts:user_list", "get", 403),
    ("no_role", "accounts:user_list", "get", 403),
    ("anonymous", "accounts:user_list", "get", 302),
    # 角色管理
    ("superadmin", "rbac:role_list", "get", 200),
    ("sysadmin", "rbac:role_list", "get", 200),
    ("cs_manager", "rbac:role_list", "get", 403),
    ("cs_staff", "rbac:role_list", "get", 403),
    ("no_role", "rbac:role_list", "get", 403),
    ("anonymous", "rbac:role_list", "get", 302),
    # 工单列表
    ("superadmin", "tickets:list", "get", 200),
    ("sysadmin", "tickets:list", "get", 200),
    ("cs_manager", "tickets:list", "get", 200),
    ("cs_staff", "tickets:list", "get", 200),
    ("no_role", "tickets:list", "get", 403),
    ("anonymous", "tickets:list", "get", 302),
    # 工单导出（只有主管有）
    ("superadmin", "tickets:export", "get", 200),
    ("sysadmin", "tickets:export", "get", 403),
    ("cs_manager", "tickets:export", "get", 200),
    ("cs_staff", "tickets:export", "get", 403),
    # 审计日志
    ("superadmin", "audit:log_list", "get", 200),
    ("sysadmin", "audit:log_list", "get", 200),
    ("cs_manager", "audit:log_list", "get", 403),
    ("cs_staff", "audit:log_list", "get", 403),
]


@pytest.mark.parametrize(
    "user_key,url_name,method,expected",
    FUNCTIONAL_MATRIX,
    ids=[f"{u}-{r.split(':')[-1]}-{m}" for u, r, m, _ in FUNCTIONAL_MATRIX],
)
@pytest.mark.django_db
def test_functional_permission_matrix(as_user, user_key, url_name, method, expected):
    client = as_user(user_key)
    url = reverse(url_name)
    resp = getattr(client, method)(url)
    assert resp.status_code == expected, (
        f"{user_key} {method.upper()} {url} -> {resp.status_code}，期望 {expected}"
    )


# --------------------------------------------------------------------------- #
# 数据权限矩阵
# --------------------------------------------------------------------------- #

SCOPE_MATRIX = [
    ("superadmin", 80),  # 超管绕过一切
    ("sysadmin", 80),    # data_scope = ALL
    ("cs_manager", 50),  # 客服部及三个子组
    ("cs_staff", 5),     # 仅本人创建
    ("no_role", 0),      # ⚠️ 默认拒绝，不是 80
]


@pytest.mark.parametrize("user_key,expected", SCOPE_MATRIX, ids=[u for u, _ in SCOPE_MATRIX])
@pytest.mark.django_db
def test_data_scope_matrix(world, user_key, expected):
    user = world[user_key]
    assert Ticket.objects.for_user(user).count() == expected, (
        f"{user_key} 的可见工单数不符：期望 {expected}"
    )


@pytest.mark.parametrize("user_key,expected", SCOPE_MATRIX, ids=[u for u, _ in SCOPE_MATRIX])
@pytest.mark.django_db
def test_list_page_count_matches_scope(as_user, world, user_key, expected):
    """页面上显示的数量必须和 ORM 层一致——两条路径不能对不上账。"""
    client = as_user(user_key)
    resp = client.get(reverse("tickets:list"))
    if resp.status_code == 403:
        assert expected == 0
        return
    assert resp.context["page"].paginator.count == expected


# --------------------------------------------------------------------------- #
# 跨部门访问（IDOR）矩阵
# --------------------------------------------------------------------------- #

CROSS_DEPT_MATRIX = [
    ("superadmin", 200),  # 超管可见
    ("sysadmin", 200),    # ALL 范围可见
    ("cs_manager", 404),  # 范围外 -> 404（不是 403，避免泄露存在性）
    ("cs_staff", 404),
    ("no_role", 403),     # 连 view 权限都没有，先被功能权限挡住
    ("anonymous", 302),
]


@pytest.mark.parametrize(
    "user_key,expected", CROSS_DEPT_MATRIX, ids=[u for u, _ in CROSS_DEPT_MATRIX]
)
@pytest.mark.django_db
def test_cross_department_ticket_access(as_user, world, user_key, expected):
    tech_ticket = Ticket.objects.filter(department=world["tech"]).first()
    client = as_user(user_key)
    resp = client.get(reverse("tickets:detail", args=[tech_ticket.pk]))
    assert resp.status_code == expected


# --------------------------------------------------------------------------- #
# 角色继承的实际效果
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestInheritanceInMatrix:
    def test_manager_inherits_specialist_perms(self, world):
        from apps.rbac.services import get_user_perm_codes

        manager_codes = get_user_perm_codes(world["cs_manager"])
        specialist_codes = get_user_perm_codes(world["cs_staff"])

        assert specialist_codes <= manager_codes  # child ⊇ parent
        assert "ticket:ticket:delete" in manager_codes
        assert "ticket:ticket:delete" not in specialist_codes

    def test_adding_perm_to_parent_reaches_child(self, world):
        from apps.rbac.models import Permission, RolePermission
        from apps.rbac.services import get_user_perm_codes

        RolePermission.objects.create(
            role=world["roles"]["specialist"],
            permission=Permission.objects.get(code="system:perm:view"),
        )

        manager = type(world["cs_manager"]).objects.get(pk=world["cs_manager"].pk)
        assert "system:perm:view" in get_user_perm_codes(manager)


# --------------------------------------------------------------------------- #
# 覆盖完整性：矩阵是否覆盖了所有受控端点
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_matrix_covers_every_menu_endpoint():
    """所有出现在菜单里的页面，都必须在功能权限矩阵中被覆盖。

    加了新页面却忘了加矩阵行 -> 测试变红。
    """
    from apps.rbac.checks import _iter_views, _unwrap

    build_demo_world()
    covered = {row[1] for row in FUNCTIONAL_MATRIX}

    from django.urls import get_resolver

    listed = set()
    for _route, view in _iter_views():
        target = _unwrap(view)
        code = getattr(target, "_required_perm", None)
        # 只要求覆盖「菜单级」页面（权限码以 :view 结尾且有对应 URL name）
        if code and code.endswith(":view"):
            for name, entries in get_resolver().reverse_dict.items():
                if isinstance(name, str) and entries[0][0][0] == _route.replace(
                    "<int:pk>", "%(pk)s"
                ):
                    listed.add(name)

    missing = {n for n in listed if n not in covered}
    assert not missing, f"这些菜单页面没有进越权矩阵：{sorted(missing)}"


@pytest.mark.django_db
def test_demo_world_shape(world):
    """演示数据的形状是矩阵断言的前提，先把它钉住。"""
    assert Ticket.objects.count() == 80
    assert Ticket.objects.filter(department=world["tech"]).count() == 30
    assert Ticket.objects.filter(creator=world["cs_staff"]).count() == 5
    assert world["cs_manager"].department == world["cs"]
    assert world["cs_staff"].department == world["cs1"]
    assert world["roles"]["manager"].inherits_from == world["roles"]["specialist"]
