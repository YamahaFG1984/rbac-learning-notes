"""把权限码导出成前端的 TypeScript 常量（F-ADR-012）。

这是后端 ADR-004「权限点在代码里声明」的延续，也补上了模板版的一个已知缺口：

    v0.10.0 陷阱 3：模板里的权限码 typo 不会报错，只会**静默地不渲染按钮**。
    管理员配好了权限，用户却看不到按钮，排查时你会怀疑缓存、怀疑角色配置、
    怀疑数据库——就是想不到是少打了一个字母。

模板版靠 `sync_permissions --check-templates` 事后扫描（v1.0.0）；
**TypeScript 可以在编译期就挡住**——这是 SPA 相比模板版
唯一在权限安全性上更强的地方，值得利用。
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.rbac.models import Permission

HEADER = """// ⚙️ 此文件由 `python manage.py export_perm_constants` 生成，请勿手工编辑。
//
// 后端权限点变更后重新生成；CI 会校验它与后端一致。
// 用法：<Can perm={PERM.TICKET_TICKET_DELETE}>
//
// perm 的类型是 PermCode 而不是 string —— 写错的权限码**编译期就报错**，
// 不会像模板版那样静默地不渲染按钮（F-ADR-012）。
"""


class Command(BaseCommand):
    help = "把权限码导出为前端 TS 常量"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="只校验现有文件是否与数据库一致，不写入（CI 用）",
        )

    def handle(self, *args, **options):
        rows = list(
            Permission.objects.exclude(code__isnull=True)
            .exclude(code="")
            .exclude(is_deprecated=True)
            .order_by("code")
            .values_list("code", "name")
        )

        lines = [HEADER, "export const PERM = {"]
        for code, name in rows:
            const = code.upper().replace(":", "_").replace("-", "_")
            lines.append(f"  /** {name} */")
            lines.append(f"  {const}: '{code}',")
        lines += [
            # ⚠️ as const 不能少 —— 没有它类型会被推断成 string，收窄完全失效，
            #    而且不会报任何错。
            "} as const",
            "",
            "export type PermCode = (typeof PERM)[keyof typeof PERM]",
            "",
        ]
        content = "\n".join(lines)

        target = Path(settings.BASE_DIR, "frontend/src/constants/permissions.ts")

        if options["check"]:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != content:
                self.stdout.write(
                    self.style.ERROR(
                        "frontend/src/constants/permissions.ts 与后端权限点不一致。\n"
                        "请运行 `python manage.py export_perm_constants` 后提交。"
                    )
                )
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS("权限常量与后端一致"))
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"已写入 {target.name}（{len(rows)} 个权限码）")
        )
