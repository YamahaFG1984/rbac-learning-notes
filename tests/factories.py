"""标准演示数据集。

与 v1.0.0 的 `seed_demo` 管理命令保持一致——演示时看到的和测试断言的
必须是同一套数据，否则「跑一遍演示」证明不了什么。

    总部 (HQ)
    ├── 客服部 (CS)
    │   ├── 客服一组 (CS1)
    │   ├── 客服二组 (CS2)
    │   └── 客服三组 (CS3)
    └── 技术部 (TECH)

    工单 80 张：客服部树下 50 张（cs_staff 创建 5 张），技术部 30 张。
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.accounts.models import Department
from apps.audit.permissions import AuditPerm
from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.tickets.models import Ticket
from apps.tickets.permissions import TicketPerm

User = get_user_model()

DEMO_PASSWORD = "demo1234"


def _role(code, name, *perm_codes, scope=DataScope.SELF_ONLY, inherits_from=None):
    role = Role.objects.create(
        code=code, name=name, data_scope=scope, inherits_from=inherits_from
    )
    for pc in perm_codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=pc))
    return role


def build_demo_world():
    """构造标准演示数据，返回一个 dict。"""
    call_command("sync_permissions", verbosity=0)

    hq = Department.objects.create(code="HQ", name="总部", order_num=10)
    cs = Department.objects.create(code="CS", name="客服部", parent=hq, order_num=10)
    cs1 = Department.objects.create(code="CS1", name="客服一组", parent=cs, order_num=10)
    cs2 = Department.objects.create(code="CS2", name="客服二组", parent=cs, order_num=20)
    cs3 = Department.objects.create(code="CS3", name="客服三组", parent=cs, order_num=30)
    tech = Department.objects.create(code="TECH", name="技术部", parent=hq, order_num=20)

    sysadmin_role = _role(
        "sysadmin",
        "系统管理员",
        "system:dept:view", "system:dept:create", "system:dept:update", "system:dept:delete",
        "system:user:view", "system:user:create", "system:user:update",
        "system:user:delete", "system:user:assign_role",
        "system:role:view", "system:role:create", "system:role:update",
        "system:role:delete", "system:role:assign_perm",
        "system:perm:view",
        AuditPerm.VIEW,
        TicketPerm.VIEW,
        scope=DataScope.ALL,
    )
    specialist_role = _role(
        "cs_specialist",
        "客服专员",
        TicketPerm.VIEW, TicketPerm.CREATE, TicketPerm.UPDATE,
        scope=DataScope.SELF_ONLY,
    )
    manager_role = _role(
        "cs_manager",
        "客服主管",
        TicketPerm.ASSIGN, TicketPerm.EXPORT, TicketPerm.DELETE,
        scope=DataScope.DEPT_AND_BELOW,
        inherits_from=specialist_role,
    )
    empty_role = _role("empty", "无权限角色", scope=DataScope.SELF_ONLY)

    def user(username, dept, *roles, **kw):
        u = User.objects.create_user(
            username=username, password=DEMO_PASSWORD, department=dept, **kw
        )
        for r in roles:
            UserRole.objects.create(user=u, role=r)
        return u

    superadmin = User.objects.create_superuser(
        username="superadmin", password=DEMO_PASSWORD, real_name="超级管理员", department=hq
    )
    sysadmin = user("sysadmin", hq, sysadmin_role, real_name="系统管理员")
    cs_manager = user("cs_manager", cs, manager_role, real_name="王主管")
    cs_staff = user("cs_staff", cs1, specialist_role, real_name="李专员")
    no_role = user("no_role", cs1, real_name="新人")
    techie = user("techie", tech, specialist_role, real_name="技术同学")

    tickets = []
    for i in range(5):
        tickets.append(Ticket(title=f"我的单-{i}", creator=cs_staff, department=cs1))
    for i in range(15):
        tickets.append(Ticket(title=f"客服一组-{i}", creator=cs_manager, department=cs1))
    for i in range(15):
        tickets.append(Ticket(title=f"客服二组-{i}", creator=cs_manager, department=cs2))
    for i in range(5):
        tickets.append(Ticket(title=f"客服三组-{i}", creator=cs_manager, department=cs3))
    for i in range(10):
        tickets.append(Ticket(title=f"客服部-{i}", creator=cs_manager, department=cs))
    for i in range(30):
        tickets.append(Ticket(title=f"技术部-{i}", creator=techie, department=tech))
    Ticket.objects.bulk_create(tickets)

    return {
        "hq": hq, "cs": cs, "cs1": cs1, "cs2": cs2, "cs3": cs3, "tech": tech,
        "superadmin": superadmin,
        "sysadmin": sysadmin,
        "cs_manager": cs_manager,
        "cs_staff": cs_staff,
        "no_role": no_role,
        "techie": techie,
        "roles": {
            "sysadmin": sysadmin_role,
            "specialist": specialist_role,
            "manager": manager_role,
            "empty": empty_role,
        },
    }
