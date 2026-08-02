"""导出**服务端真正在校验**的权限码清单。

🔴 它补上的是 F-ADR-012 的另一半。

`export_perm_constants` 导出的是「系统里存在哪些权限码」——
它能挡住 typo，但挡不住这个：

    <Can perm={PERM.TICKET_TICKET_DELETE}>   ← 前端藏了按钮
    # 后端的 destroy 忘了写进 perm_map      ← 服务端根本没拦

权限码存在、TypeScript 编译通过、界面看起来完全正确，
而那个接口是裸奔的。

CLAUDE.md 安全红线 2：
    模板隐藏按钮不是安全边界。每一个受控按钮，必须有对应的服务端校验。
    **成对出现，缺一不可。**

「成对出现」这件事光靠人看是守不住的。这个命令把服务端那一半导出来，
前端的结构性测试拿它对账（frontend/tests/structural/permCoverage.test.ts）。

⚠️ 它导出的是「哪些码在服务端被用于判断」，**不是**「哪个接口用了哪个码」。
   后者需要把路由也带上，对账会精确得多，但那是另一个量级的工作。
   现在这一版能抓住「前端管了、后端完全没管」这类漏，抓不住
   「后端管了，但管在了另一个接口上」。**知道自己抓不住什么，比假装全覆盖好。**
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.rbac.checks import _iter_views, _unwrap


def collect_enforced_codes() -> set[str]:
    """扫描全部路由，收集服务端实际用于判断的权限码。

    两个来源：
      · 模板视图的 @require_perm / @require_any_perm（挂在函数属性上）
      · DRF ViewSet 的 perm_map（HasPerm 读它）

    ⚠️ 复用 checks.py 的 _iter_views / _unwrap，不另写一套遍历——
       另写一套的话，rbac.W001 能看到的视图和这里能看到的视图会不一致，
       而不一致的那部分正好是最容易出漏洞的地方。
    """
    codes: set[str] = set()

    for _route, view in _iter_views():
        # 模板视图
        target = _unwrap(view)
        single = getattr(target, "_required_perm", None) or getattr(
            target, "required_perm", None
        )
        if single:
            codes.add(single)
        for attr in ("_required_any_perms", "required_any_perms"):
            for code in getattr(target, attr, None) or ():
                codes.add(code)

        # DRF ViewSet
        cls = getattr(view, "view_class", None) or getattr(view, "cls", None)
        for code in (getattr(cls, "perm_map", None) or {}).values():
            if code:
                codes.add(code)

    return codes


class Command(BaseCommand):
    help = "导出服务端实际校验的权限码清单（供前端结构性测试对账）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="只校验现有文件是否最新，不写入（CI 用）",
        )

    def handle(self, *args, **options):
        codes = sorted(collect_enforced_codes())
        payload = {
            "_comment": (
                "由 `python manage.py export_enforced_perms` 生成，请勿手工编辑。"
                "内容是服务端实际用于权限判断的权限码。"
            ),
            "enforced": codes,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

        target = Path(settings.BASE_DIR, "frontend/src/test/enforced-perms.json")

        if options["check"]:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != content:
                self.stdout.write(
                    self.style.ERROR(
                        "frontend/src/test/enforced-perms.json 已过期。\n"
                        "请运行 `python manage.py export_enforced_perms` 后提交。"
                    )
                )
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS("服务端校验清单是最新的"))
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"已写入 {target.name}（{len(codes)} 个权限码）")
        )
