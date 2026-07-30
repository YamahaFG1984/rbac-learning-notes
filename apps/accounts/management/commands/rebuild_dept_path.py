"""重建部门树的 path / depth 冗余字段。

path 是冗余数据，理论上可能与 parent 不一致——有人直接改数据库、
用 bulk_create 绕过 save()、或迁移脚本里改了数据。

本命令**只信任 parent**，从根开始逐层重算，保证「无论当前 path 多乱，跑完都对」。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Department


class Command(BaseCommand):
    help = "根据 parent 关系重建全部部门的 path 与 depth"

    @transaction.atomic
    def handle(self, *args, **options):
        nodes = list(Department.objects.all())
        children_of = {}
        for n in nodes:
            children_of.setdefault(n.parent_id, []).append(n)

        updated = []

        def walk(parent_id, parent_path, depth):
            for node in children_of.get(parent_id, []):
                node.path = f"{parent_path}{node.pk}/"
                node.depth = depth
                updated.append(node)
                walk(node.pk, node.path, depth + 1)

        walk(None, "/", 0)

        if updated:
            Department.objects.bulk_update(updated, ["path", "depth"])

        orphans = len(nodes) - len(updated)
        self.stdout.write(self.style.SUCCESS(f"已重建 {len(updated)} 个部门的 path/depth"))
        if orphans:
            self.stdout.write(
                self.style.WARNING(f"⚠️ 有 {orphans} 个节点未能从根到达（可能存在环）")
            )
