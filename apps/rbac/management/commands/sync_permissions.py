"""把各 app 的 permissions.py 中声明的权限点幂等地同步进数据库。

幂等的定义：跑第二次时输出必须是「新增 0，更新 0」。

⚠️ 绝不能先 delete_all 再重建——主键会全变，已有的角色-权限授权
   会全部失效。这是灾难性的。
"""

import re
from importlib import import_module

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.rbac.constants import ALLOWED_ACTIONS, PERM_CODE_PATTERN, PermType
from apps.rbac.models import Permission

CODE_RE = re.compile(PERM_CODE_PATTERN)

# 只匹配三段式格式的字符串字面量。太宽会误报（CSS 里的 background:url:xxx），
# 太窄会漏报。
TEMPLATE_CODE_RE = re.compile(
    r"""['"]([a-z][a-z0-9_]*:[a-z][a-z0-9_]*:[a-z][a-z0-9_]*)['"]\s+in\s+perms"""
)


def collect_permissions():
    """发现所有 apps.* 下的 permissions.py 并收集其 PERMISSIONS 声明。"""
    result = []
    for config in apps.get_app_configs():
        if not config.name.startswith("apps."):
            continue
        try:
            mod = import_module(f"{config.name}.permissions")
        except ModuleNotFoundError:
            continue
        result.extend(getattr(mod, "PERMISSIONS", []))
    return result


class Command(BaseCommand):
    help = "同步代码中声明的权限点到数据库（幂等）"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只报告，不写库")
        parser.add_argument(
            "--check-frontend",
            action="store_true",
            help="校验菜单的 component 指向的前端文件是否存在",
        )
        parser.add_argument(
            "--check-templates",
            action="store_true",
            help="扫描模板中的权限码字面量，报告数据库里不存在的",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.stats = {"created": 0, "updated": 0, "deprecated": 0, "unchanged": 0}
        self.seen_codes = set()

        tree = collect_permissions()
        self._validate(tree)

        for node in sorted(tree, key=lambda n: n.get("order", 0)):
            self._sync_node(node, parent=None)

        # 代码里没了但库里还有 -> 标记废弃，不物理删除（FR-2.6）
        stale = Permission.objects.exclude(code__isnull=True).exclude(
            code__in=self.seen_codes
        ).filter(is_deprecated=False)
        self.stats["deprecated"] = stale.count()
        if not self.dry_run:
            stale.update(is_deprecated=True)

        self.stdout.write(
            self.style.SUCCESS(
                "新增 {created} 个，更新 {updated} 个，标记废弃 {deprecated} 个"
                "（未变化 {unchanged} 个）".format(**self.stats)
            )
        )
        # queryset.update() 不触发 post_save 信号，显式失效一次
        if not self.dry_run:
            from apps.rbac.cache import bump_version

            bump_version()

        if options["check_frontend"]:
            problems = self._check_frontend()
            if problems and not self.dry_run:
                raise SystemExit(1)

        if options["check_templates"]:
            problems = self._check_templates()
            if problems and not self.dry_run:
                raise SystemExit(1)

        if self.dry_run:
            transaction.set_rollback(True)

    # ------------------------------------------------------------------ #

    def _check_templates(self):
        """扫描模板里的权限码字面量，报告数据库里不存在的。

        解决 v0.10.0 留下的问题：模板里写错权限码不会报错，
        只会**静默地不渲染那个按钮**。管理员配好了权限，用户却看不到按钮，
        排查时你会怀疑缓存、怀疑角色配置、怀疑数据库——就是想不到
        是模板里少打了一个字母。

        ⚠️ 它只能发现「模板里有但库里没有」的。发现不了「库里有但
           写错成了另一个存在的码」——部分解决好过不解决。
        """
        from pathlib import Path

        from django.conf import settings

        known = set(
            Permission.objects.exclude(code__isnull=True).values_list("code", flat=True)
        )
        problems = []
        for path in sorted(Path(settings.BASE_DIR, "templates").rglob("*.html")):
            text = path.read_text(encoding="utf-8")
            for match in TEMPLATE_CODE_RE.finditer(text):
                code = match.group(1)
                if code not in known:
                    line = text[: match.start()].count("\n") + 1
                    rel = path.relative_to(settings.BASE_DIR)
                    problems.append(f"{rel}:{line}  {code}")

        if problems:
            self.stdout.write(self.style.ERROR(f"发现 {len(problems)} 个未知权限码："))
            for p in problems:
                self.stdout.write(f"  {p}")
        else:
            self.stdout.write(self.style.SUCCESS("模板中的权限码全部有效"))
        return problems

    def _check_frontend(self):
        """校验菜单的 component 指向的前端文件确实存在。

        ⚠️ 它只能发现「写成了 tickets/Lst」这类拼错，
           发现不了「写成了另一个真实存在但不对的组件」。
           部分解决好过不解决——同 v1.0.0 的 --check-templates。
        """
        from pathlib import Path

        from django.conf import settings

        pages = Path(settings.BASE_DIR, "frontend/src/pages")
        problems = []
        for perm in Permission.objects.exclude(component="").order_by("code"):
            target = pages / f"{perm.component}.tsx"
            if not target.exists():
                problems.append(f"{perm.code or perm.name}  ->  {perm.component}.tsx")

        if problems:
            self.stdout.write(self.style.ERROR(f"发现 {len(problems)} 个无效的前端组件："))
            for item in problems:
                self.stdout.write(f"  {item}")
        else:
            self.stdout.write(self.style.SUCCESS("菜单的前端组件全部存在"))
        return problems

    def _validate(self, nodes, _path="根"):
        """让机器守规范：格式不对直接报错，不要等到某天鉴权失败再 grep 半天。"""
        for node in nodes:
            code = node.get("code")
            if code is not None:
                if not CODE_RE.match(code):
                    raise ValueError(
                        f"权限码格式非法：{code!r}（应为 app:resource:action，全小写下划线）"
                    )
                action = code.rsplit(":", 1)[-1]
                if action not in ALLOWED_ACTIONS:
                    raise ValueError(
                        f"权限码 {code!r} 的 action {action!r} 不在受控词表中：\n"
                        f"  {sorted(ALLOWED_ACTIONS)}\n"
                        f"  需要新动词请先在设计文档 ADR-004 的表里加。"
                    )
            elif node.get("type") != PermType.CATALOG:
                raise ValueError(f"只有 catalog 类型可以没有权限码：{node.get('name')!r}")
            self._validate(node.get("children", []), _path=node.get("name", ""))

    def _sync_node(self, node, parent):
        code = node.get("code")
        defaults = {
            "name": node["name"],
            "perm_type": node["type"],
            "parent": parent,
            "order_num": node.get("order", 0),
            "url_name": node.get("url_name", ""),
            "route_path": node.get("route_path", ""),
            "component": node.get("component", ""),
            "icon": node.get("icon", ""),
            "is_visible": node.get("visible", True),
            "is_active": True,
            "is_deprecated": False,  # 代码里又出现了 -> 取消废弃标记
        }

        if code:
            self.seen_codes.add(code)
            lookup = {"code": code}
        else:
            # catalog 无 code，用 (parent, name, type) 作幂等键
            lookup = {"parent": parent, "name": node["name"], "perm_type": PermType.CATALOG}

        obj = Permission.objects.filter(**lookup).first()
        if obj is None:
            if self.dry_run:
                self.stats["created"] += 1
                obj = Permission(**{**lookup, **defaults})  # 供子节点挂载，不入库
            else:
                obj = Permission.objects.create(**{**lookup, **defaults})
                self.stats["created"] += 1
        else:
            # 先比对再决定是否写——update_or_create 会把「值没变」也计成 updated，
            # 那样永远做不到真正的「0 更新」。
            changed = [f for f, v in defaults.items() if getattr(obj, f) != v]
            if changed:
                for f, v in defaults.items():
                    setattr(obj, f, v)
                if not self.dry_run:
                    obj.save()
                self.stats["updated"] += 1
            else:
                self.stats["unchanged"] += 1

        for child in sorted(node.get("children", []), key=lambda n: n.get("order", 0)):
            self._sync_node(child, parent=obj)
