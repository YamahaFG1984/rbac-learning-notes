import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from apps.accounts.models import Department


@pytest.fixture
def tree(db):
    """总部 -> 客服部 -> 客服一组"""
    hq = Department.objects.create(code="HQ", name="总部")
    cs = Department.objects.create(code="CS", name="客服部", parent=hq)
    cs1 = Department.objects.create(code="CS1", name="客服一组", parent=cs)
    return hq, cs, cs1


@pytest.mark.django_db
class TestPathMaintenance:
    def test_path_and_depth_on_create(self, tree):
        hq, cs, cs1 = tree
        assert hq.path == f"/{hq.pk}/"
        assert cs.path == f"/{hq.pk}/{cs.pk}/"
        assert cs1.path == f"/{hq.pk}/{cs.pk}/{cs1.pk}/"
        assert (hq.depth, cs.depth, cs1.depth) == (0, 1, 2)

    def test_move_cascades_to_subtree(self, tree):
        hq, cs, cs1 = tree
        tech = Department.objects.create(code="TECH", name="技术部")

        cs.parent = tech
        cs.save()
        cs1.refresh_from_db()

        assert cs.path == f"/{tech.pk}/{cs.pk}/"
        assert cs1.path == f"/{tech.pk}/{cs.pk}/{cs1.pk}/"
        assert cs.depth == 1
        assert cs1.depth == 2

    def test_move_uses_bulk_update_not_recursion(self, tree, django_assert_num_queries):
        """移动节点的写操作次数与子树大小无关。"""
        hq, cs, cs1 = tree
        for i in range(10):
            Department.objects.create(code=f"X{i}", name=f"组{i}", parent=cs1)

        tech = Department.objects.create(code="TECH", name="技术部")
        # 4 = super().save() 的 UPDATE
        #   + 自身 path/depth 的 UPDATE
        #   + 子树 SELECT
        #   + 子树 bulk_update
        # 关键：这个数字与子树大小无关。改成递归 save() 会变成 O(n)。
        with django_assert_num_queries(4):
            cs.parent = tech
            cs.save()


@pytest.mark.django_db
class TestGetDescendants:
    def test_includes_self_by_default(self, tree):
        hq, cs, cs1 = tree
        assert set(cs.get_descendants().values_list("pk", flat=True)) == {cs.pk, cs1.pk}
        assert set(cs.get_descendants(include_self=False).values_list("pk", flat=True)) == {cs1.pk}

    def test_single_query(self, tree, django_assert_num_queries):
        hq, _, _ = tree
        with django_assert_num_queries(1):
            list(hq.get_descendants())

    def test_id_prefix_trap(self, db):
        """⚠️ path 尾斜杠的正确性测试。

        "/11/".startswith("/1")  -> True   部门 11 会被误判为部门 1 的后代
        "/11/".startswith("/1/") -> False  正确

        造一批部门让 ID 跨到两位数，断言 ID=1 的子树不含 ID=11 的无关部门。
        """
        roots = [Department.objects.create(code=f"R{i}", name=f"根{i}") for i in range(12)]
        first, eleventh = roots[0], roots[10]
        # 确认确实构造出了 ID 前缀关系（如 1 和 11）
        assert str(eleventh.pk).startswith(str(first.pk))

        descendants = set(first.get_descendants().values_list("pk", flat=True))
        assert descendants == {first.pk}
        assert eleventh.pk not in descendants

    def test_get_ancestors(self, tree):
        hq, cs, cs1 = tree
        assert set(cs1.get_ancestors().values_list("pk", flat=True)) == {hq.pk, cs.pk}
        assert set(cs1.get_ancestors(include_self=True).values_list("pk", flat=True)) == {
            hq.pk,
            cs.pk,
            cs1.pk,
        }


@pytest.mark.django_db
class TestConstraints:
    def test_delete_with_children_protected(self, tree):
        hq, cs, cs1 = tree
        with pytest.raises(ProtectedError):
            cs.delete()

    def test_delete_with_users_protected(self, tree, django_user_model):
        hq, cs, cs1 = tree
        django_user_model.objects.create_user(username="u1", password="x", department=cs1)
        with pytest.raises(ProtectedError):
            cs1.delete()

    def test_queryset_delete_also_protected(self, tree):
        """PROTECT 在批量删除路径下同样生效——这正是选它而非在 delete() 里写检查的原因。"""
        hq, cs, cs1 = tree
        with pytest.raises(ProtectedError):
            Department.objects.filter(pk=cs.pk).delete()

    def test_cannot_move_into_own_descendant(self, tree):
        hq, cs, cs1 = tree
        hq.parent = cs1
        with pytest.raises(ValidationError):
            hq.full_clean()

    def test_cannot_be_own_parent(self, tree):
        hq, _, _ = tree
        hq.parent = hq
        with pytest.raises(ValidationError):
            hq.full_clean()


@pytest.mark.django_db
class TestRebuildCommand:
    def test_rebuild_fixes_corrupted_path(self, tree):
        from django.core.management import call_command

        hq, cs, cs1 = tree
        # 模拟脏数据：直接改库绕过 save()
        Department.objects.filter(pk=cs1.pk).update(path="/garbage/", depth=99)

        call_command("rebuild_dept_path")

        cs1.refresh_from_db()
        assert cs1.path == f"/{hq.pk}/{cs.pk}/{cs1.pk}/"
        assert cs1.depth == 2
