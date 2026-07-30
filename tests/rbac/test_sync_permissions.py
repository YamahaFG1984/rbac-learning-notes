import pytest
from django.core.management import call_command

from apps.rbac.constants import PermType
from apps.rbac.models import Permission


def sync(**kwargs):
    from io import StringIO

    out = StringIO()
    call_command("sync_permissions", stdout=out, **kwargs)
    return out.getvalue().strip()


@pytest.mark.django_db
class TestIdempotency:
    def test_first_run_creates(self):
        out = sync()
        assert "更新 0 个" in out
        assert Permission.objects.count() > 0

    def test_second_run_is_noop(self):
        """幂等：跑第二次必须是 0 新增 0 更新。"""
        sync()
        count = Permission.objects.count()
        out = sync()
        assert "新增 0 个，更新 0 个，标记废弃 0 个" in out
        assert Permission.objects.count() == count

    def test_pks_are_stable(self):
        """绝不能先删后建——主键变了，已有的角色-权限授权会全部失效。"""
        sync()
        before = dict(
            Permission.objects.exclude(code__isnull=True).values_list("code", "id")
        )
        sync()
        after = dict(
            Permission.objects.exclude(code__isnull=True).values_list("code", "id")
        )
        assert before == after


@pytest.mark.django_db
class TestDeprecation:
    def test_removed_code_is_marked_not_deleted(self, monkeypatch):
        sync()
        target = Permission.objects.filter(code="system:dept:delete").first()
        assert target is not None

        # 模拟「代码里删掉了这个权限点」
        import apps.accounts.permissions as ap

        pruned = _drop_code(ap.PERMISSIONS, "system:dept:delete")
        monkeypatch.setattr(ap, "PERMISSIONS", pruned)

        out = sync()
        assert "标记废弃 1 个" in out

        target.refresh_from_db()
        assert target.is_deprecated is True  # 数据仍在，只是被标记

    def test_readded_code_clears_deprecated(self, monkeypatch):
        sync()
        Permission.objects.filter(code="system:dept:delete").update(is_deprecated=True)
        sync()
        assert (
            Permission.objects.get(code="system:dept:delete").is_deprecated is False
        )


@pytest.mark.django_db
class TestValidation:
    def test_rejects_malformed_code(self, monkeypatch):
        import apps.accounts.permissions as ap

        monkeypatch.setattr(
            ap,
            "PERMISSIONS",
            [{"code": "Ticket:View", "name": "坏码", "type": "button", "order": 1}],
        )
        with pytest.raises(ValueError, match="格式非法"):
            sync()

    def test_rejects_unknown_action(self, monkeypatch):
        import apps.accounts.permissions as ap

        monkeypatch.setattr(
            ap,
            "PERMISSIONS",
            [{"code": "system:dept:frobnicate", "name": "怪动词", "type": "button"}],
        )
        with pytest.raises(ValueError, match="不在受控词表"):
            sync()

    def test_rejects_non_catalog_without_code(self, monkeypatch):
        import apps.accounts.permissions as ap

        monkeypatch.setattr(
            ap, "PERMISSIONS", [{"code": None, "name": "无码菜单", "type": "menu"}]
        )
        with pytest.raises(ValueError, match="只有 catalog"):
            sync()


@pytest.mark.django_db
class TestStructure:
    def test_catalog_has_null_code(self):
        sync()
        catalogs = Permission.objects.filter(perm_type=PermType.CATALOG)
        assert catalogs.count() >= 2
        assert all(c.code is None for c in catalogs)

    def test_multiple_null_codes_allowed(self):
        """SQL 标准：NULL != NULL，所以 unique 索引允许多行 NULL。
        用空串代替 NULL 的话，第二个 catalog 就会撞唯一约束。"""
        sync()
        assert Permission.objects.filter(code__isnull=True).count() >= 2

    def test_tree_paths_built(self):
        sync()
        for p in Permission.objects.all():
            assert p.path.startswith("/") and p.path.endswith("/")
            assert p.depth == p.path.count("/") - 2

    def test_dry_run_writes_nothing(self):
        out = sync(dry_run=True)
        assert "新增" in out
        assert Permission.objects.count() == 0


def _drop_code(nodes, code):
    """返回移除了指定 code 的权限树副本。"""
    result = []
    for n in nodes:
        if n.get("code") == code:
            continue
        copy = dict(n)
        copy["children"] = _drop_code(n.get("children", []), code)
        result.append(copy)
    return result
