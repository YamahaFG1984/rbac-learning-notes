"""数据权限。全项目最容易写出安全漏洞的地方。

四处「默认拒绝」在正常使用中永远不会被触发——只有这些测试能保证它们是对的，
也只有这些测试能阻止它们在未来被误删。
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command

from apps.accounts.models import Department
from apps.rbac.constants import DataScope
from apps.rbac.models import Role, UserRole
from apps.rbac.services import build_scope_q, get_user_dept_ids
from apps.tickets.models import Ticket


@pytest.fixture
def perms(db):
    call_command("sync_permissions", verbosity=0)


@pytest.fixture
def org(db):
    """总部
         ├── 客服部 ── 客服一组 / 客服二组 / 客服三组
         └── 技术部
    """
    hq = Department.objects.create(code="HQ", name="总部")
    cs = Department.objects.create(code="CS", name="客服部", parent=hq)
    cs1 = Department.objects.create(code="CS1", name="客服一组", parent=cs)
    cs2 = Department.objects.create(code="CS2", name="客服二组", parent=cs)
    cs3 = Department.objects.create(code="CS3", name="客服三组", parent=cs)
    tech = Department.objects.create(code="TECH", name="技术部", parent=hq)
    return {"hq": hq, "cs": cs, "cs1": cs1, "cs2": cs2, "cs3": cs3, "tech": tech}


@pytest.fixture
def world(org, django_user_model, perms):
    """80 张工单：客服部树下 50 张（cs_staff 创建 5 张），技术部 30 张。"""
    boss = django_user_model.objects.create_user(
        username="boss", password="x", department=org["cs"]
    )
    staff = django_user_model.objects.create_user(
        username="cs_staff", password="x", department=org["cs1"]
    )
    techie = django_user_model.objects.create_user(
        username="techie", password="x", department=org["tech"]
    )

    made = []
    for i in range(5):
        made.append(Ticket(title=f"self{i}", creator=staff, department=org["cs1"]))
    for i in range(15):
        made.append(Ticket(title=f"cs1-{i}", creator=boss, department=org["cs1"]))
    for i in range(15):
        made.append(Ticket(title=f"cs2-{i}", creator=boss, department=org["cs2"]))
    for i in range(5):
        made.append(Ticket(title=f"cs3-{i}", creator=boss, department=org["cs3"]))
    for i in range(10):
        made.append(Ticket(title=f"cs-{i}", creator=boss, department=org["cs"]))
    for i in range(30):
        made.append(Ticket(title=f"tech-{i}", creator=techie, department=org["tech"]))
    Ticket.objects.bulk_create(made)

    assert Ticket.objects.count() == 80
    return {"boss": boss, "staff": staff, "techie": techie, **org}


def assign(user, scope):
    role = Role.objects.create(code=f"r{user.pk}", name="r", data_scope=scope)
    UserRole.objects.create(user=user, role=role)
    return role


# --------------------------------------------------------------------------- #
# 🔴 四处默认拒绝
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDenyByDefault:
    def test_1_anonymous_gets_empty(self, world):
        assert Ticket.objects.for_user(AnonymousUser()).count() == 0

    def test_1b_inactive_user_gets_empty(self, world):
        user = world["boss"]
        assign(user, DataScope.ALL)
        user.is_active = False
        user.save()
        assert Ticket.objects.for_user(user).count() == 0

    def test_2_user_without_role_gets_empty_not_all(self, world):
        """⚠️ 最常见也最危险的情形。

        新建用户还没配角色。写成 Q() 就是「新用户默认看到全公司 80 张工单」。
        """
        assert Ticket.objects.for_user(world["staff"]).count() == 0
        assert Ticket.objects.count() == 80  # 数据本身是有的

    def test_3_unrecognised_scope_gets_empty(self, world):
        role = assign(world["boss"], DataScope.ALL)
        Role.objects.filter(pk=role.pk).update(data_scope=99)  # 绕过 choices 校验
        assert Ticket.objects.for_user(world["boss"]).count() == 0

    def test_4_user_without_department_gets_empty(self, world):
        user = world["boss"]
        assign(user, DataScope.DEPT_AND_BELOW)
        user.department = None
        user.save()

        assert get_user_dept_ids(user) == set()
        assert Ticket.objects.for_user(user).count() == 0

    def test_q_empty_vs_q_none_semantics(self):
        """Q() 和 Q(pk__in=[]) 差两个字符，安全后果天差地别。"""
        from django.db.models import Q

        assert Ticket.objects.filter(Q()).count() == Ticket.objects.count()
        assert Ticket.objects.filter(Q(pk__in=[])).count() == 0


# --------------------------------------------------------------------------- #
# 五个枚举值
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDataScopes:
    @pytest.mark.parametrize(
        "who,scope,expected",
        [
            ("boss", DataScope.ALL, 80),
            ("boss", DataScope.DEPT_AND_BELOW, 50),  # 客服部 + 三个子组
            ("boss", DataScope.DEPT_ONLY, 10),  # 仅客服部本级
            ("staff", DataScope.SELF_ONLY, 5),  # 自己创建的
            ("staff", DataScope.DEPT_AND_BELOW, 20),  # 客服一组（叶子）
            ("techie", DataScope.DEPT_AND_BELOW, 30),
        ],
    )
    def test_scope_counts(self, world, who, scope, expected):
        user = world[who]
        assign(user, scope)
        assert Ticket.objects.for_user(user).count() == expected

    def test_superuser_sees_all(self, world, django_user_model):
        su = django_user_model.objects.create_superuser(username="su", password="x")
        assert Ticket.objects.for_user(su).count() == 80

    def test_superuser_short_circuits(self, world, django_user_model):
        su = django_user_model.objects.create_superuser(username="su", password="x")

        class Cfg:
            owner_field = "creator"
            dept_field = "department"

        assert build_scope_q(su, Cfg) is None  # None = 不过滤


# --------------------------------------------------------------------------- #
# 🔴 多角色合并：真并集，不是「取最宽枚举」
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestMultiRoleUnion:
    def test_union_not_widest_enum(self, world):
        """⚠️ 本 tag 第二个关键点。

        staff 有两个角色：
          A = SELF_ONLY(4)       -> 自己创建的 5 张
          B = DEPT_ONLY(3) 客服一组 -> 客服一组的 20 张（含自己那 5 张）

        「取最宽枚举」会按编号选 DEPT_ONLY(3)，结果 20 张——这次恰好不丢数据。
        但换成 CUSTOM(5) 参与时就会丢。真并集才是符合 RBAC 语义的做法。
        """
        staff = world["staff"]
        a = Role.objects.create(code="a", name="a", data_scope=DataScope.SELF_ONLY)
        b = Role.objects.create(code="b", name="b", data_scope=DataScope.DEPT_ONLY)
        UserRole.objects.create(user=staff, role=a)
        UserRole.objects.create(user=staff, role=b)

        assert Ticket.objects.for_user(staff).count() == 20

    def test_union_across_disjoint_sets(self, world):
        """两个互不相交的范围求并，结果必须是两者之和。

        techie（技术部）拿到「仅本人」+ 一个覆盖客服部的角色。
        取最宽枚举会丢掉其中一边。
        """
        techie = world["techie"]
        # 角色 A：仅本人 -> 技术部的 30 张（都是他创建的）
        a = Role.objects.create(code="a", name="a", data_scope=DataScope.SELF_ONLY)
        UserRole.objects.create(user=techie, role=a)
        assert Ticket.objects.for_user(techie).count() == 30

        # 角色 B：本部门及以下——但他在技术部，仍是那 30 张
        b = Role.objects.create(code="b", name="b", data_scope=DataScope.DEPT_AND_BELOW)
        UserRole.objects.create(user=techie, role=b)
        assert Ticket.objects.for_user(techie).count() == 30

    def test_all_short_circuits_other_roles(self, world):
        staff = world["staff"]
        a = Role.objects.create(code="a", name="a", data_scope=DataScope.SELF_ONLY)
        b = Role.objects.create(code="b", name="b", data_scope=DataScope.ALL)
        UserRole.objects.create(user=staff, role=a)
        UserRole.objects.create(user=staff, role=b)

        assert Ticket.objects.for_user(staff).count() == 80

    def test_inherited_role_scope_counts(self, world):
        """角色继承展开后的祖先角色，其数据范围也参与合并。"""
        staff = world["staff"]
        parent = Role.objects.create(
            code="p", name="p", data_scope=DataScope.DEPT_AND_BELOW
        )
        child = Role.objects.create(
            code="c", name="c", data_scope=DataScope.SELF_ONLY, inherits_from=parent
        )
        UserRole.objects.create(user=staff, role=child)

        assert Ticket.objects.for_user(staff).count() == 20  # 客服一组全部


# --------------------------------------------------------------------------- #
# SQL 层过滤（NFR-2）
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSqlPushdown:
    def test_filter_happens_in_where_clause(self, world):
        staff = world["staff"]
        assign(staff, DataScope.SELF_ONLY)

        sql = str(Ticket.objects.for_user(staff).query)

        assert "WHERE" in sql
        assert "creator_id" in sql

    def test_single_query_regardless_of_row_count(self, world, django_assert_num_queries):
        staff = world["staff"]
        assign(staff, DataScope.SELF_ONLY)
        # 2 = 角色展开 + 工单查询。过滤在 SQL 里完成，不是先查全量再筛。
        with django_assert_num_queries(2):
            list(Ticket.objects.for_user(staff))


# --------------------------------------------------------------------------- #
# 配置错误要立刻炸掉
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestMisconfiguration:
    def test_missing_scope_config_raises(self, world):
        from django.core.exceptions import ImproperlyConfigured

        original = Ticket.ScopeConfig
        try:
            del Ticket.ScopeConfig
            with pytest.raises(ImproperlyConfigured, match="ScopeConfig"):
                Ticket.objects.for_user(world["staff"])
        finally:
            Ticket.ScopeConfig = original


# --------------------------------------------------------------------------- #
# 视图层接入
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestViewIntegration:
    def test_list_is_scoped(self, client, world, perms):
        from apps.rbac.models import Permission, RolePermission
        from apps.tickets.permissions import TicketPerm

        staff = world["staff"]
        role = Role.objects.create(
            code="r", name="r", data_scope=DataScope.SELF_ONLY
        )
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code=TicketPerm.VIEW)
        )
        UserRole.objects.create(user=staff, role=role)
        client.force_login(staff)

        resp = client.get("/tickets/")

        # v0.13.0 时这里是 80——数据权限现在生效了
        assert resp.context["page"].paginator.count == 5
        assert "tech-0" not in resp.content.decode()
