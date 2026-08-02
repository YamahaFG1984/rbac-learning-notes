"""生成演示数据。

数据形状与 tests/factories.py 完全一致——演示时看到的和测试断言的
必须是同一套数据，否则「跑一遍演示」证明不了任何事。
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "生成演示数据（部门树 / 角色 / 用户 / 工单）"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="先清空演示数据再生成")
        parser.add_argument("--noinput", action="store_true", help="跳过确认（脚本用）")

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import Department, User
        from apps.rbac.models import Role, RoleDepartment, RolePermission, UserRole
        from apps.tickets.models import Ticket

        if options["flush"]:
            # ⚠️ 破坏性操作必须确认——防止有人在真实环境误跑
            if not options["noinput"]:
                answer = input("将清空全部演示数据（部门/角色/用户/工单），确认？(yes/no) ")
                if answer != "yes":
                    self.stdout.write("已取消")
                    return
            Ticket.objects.all().delete()
            UserRole.objects.all().delete()
            RolePermission.objects.all().delete()
            RoleDepartment.objects.all().delete()
            # ⚠️ Role.inherits_from 也是**自引用 PROTECT**，和部门树同一个形状。
            #
            #    v1.0.0 记得给部门做「从叶子往根删」（见下面几行），却漏了角色，
            #    于是 `seed_demo --flush` 直接抛 ProtectedError：
            #      Cannot delete some instances of model 'Role' because they are
            #      referenced through protected foreign keys: 'Role.inherits_from'
            #
            #    教训不是「这里忘了」，而是：**PROTECT 是一条会在删除路径上
            #    冒出来的约束，而删除路径通常是最少被走到的那条**。
            #    凡是自引用 PROTECT 外键，删除就必须自底向上——不止一处。
            while Role.objects.exists():
                leaves = Role.objects.filter(inheritors__isnull=True)
                if not leaves.exists():
                    # 走到这里说明存在环。模型层禁止了环（v0.12.0 的环检测），
                    # 真出现就是数据被手工改过——直接报错，不要静默死循环。
                    raise RuntimeError("角色继承关系中存在环，无法安全删除")
                leaves.delete()
            # ⚠️ 审计日志刻意**不清**——它只写不改不删（FR-9.4）。
            #    连 seed 脚本都不给例外，否则那条不变式就名存实亡了。
            User.objects.filter(is_superuser=False).delete()
            User.objects.filter(username="superadmin").delete()
            # 从叶子往根删，避开 PROTECT
            for dept in sorted(Department.objects.all(), key=lambda d: -d.depth):
                dept.delete()

        if Department.objects.exists():
            self.stdout.write(
                self.style.WARNING("已存在部门数据，跳过。要重新生成请加 --flush")
            )
            return

        call_command("sync_permissions", verbosity=0)

        from apps.common.demo import DEMO_PASSWORD, build_demo_world

        build_demo_world()

        self.stdout.write(self.style.SUCCESS("演示数据生成完毕"))
        self.stdout.write("")
        self.stdout.write(f"  统一密码：{DEMO_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("  账号            说明                      可见工单")
        self.stdout.write("  " + "-" * 58)
        rows = [
            ("superadmin", "超级管理员，绕过一切", 80),
            ("sysadmin", "系统管理员，data_scope=ALL", 80),
            ("cs_manager", "客服主管，继承客服专员，本部门及以下", 50),
            ("cs_staff", "客服专员，仅本人", 5),
            ("no_role", "无角色，什么都看不到", 0),
        ]
        for username, desc, count in rows:
            self.stdout.write(f"  {username:<15} {desc:<24} {count}")
        self.stdout.write("")
        self.stdout.write(f"  部门 {Department.objects.count()} 个，"
                          f"角色 {Role.objects.count()} 个，"
                          f"工单 {Ticket.objects.count()} 张")
