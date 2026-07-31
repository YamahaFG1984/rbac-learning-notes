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

        if self.dry_run:
            transaction.set_rollback(True)

    # ------------------------------------------------------------------ #

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
