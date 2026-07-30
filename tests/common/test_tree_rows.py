import pytest

from apps.accounts.models import Department
from apps.common.views import build_tree_rows


@pytest.mark.django_db
class TestBuildTreeRows:
    def test_preorder_with_order_num(self):
        root = Department.objects.create(code="R", name="根")
        b = Department.objects.create(code="B", name="乙", parent=root, order_num=20)
        a = Department.objects.create(code="A", name="甲", parent=root, order_num=10)
        a1 = Department.objects.create(code="A1", name="甲一", parent=a, order_num=10)

        names = [r["obj"].name for r in build_tree_rows(Department.objects.all())]
        assert names == ["根", "甲", "甲一", "乙"]
        assert [r["depth"] for r in build_tree_rows(Department.objects.all())] == [0, 1, 2, 1]

    def test_order_survives_two_digit_ids(self):
        """⚠️ ORDER BY path 在这里会翻车。

        path 是字符串，"/1/12/" 排在 "/1/9/" 前面（'1' < '9'）。
        真正的树序必须在内存里按 order_num 排。
        """
        root = Department.objects.create(code="R", name="根")
        for i in range(1, 13):
            Department.objects.create(
                code=f"C{i}", name=f"子{i:02d}", parent=root, order_num=i
            )

        rows = build_tree_rows(Department.objects.all())
        child_names = [r["obj"].name for r in rows if r["depth"] == 1]
        assert child_names == [f"子{i:02d}" for i in range(1, 13)]

        # 对照组：证明 ORDER BY path 确实是错的，不是我在杞人忧天
        by_path = [
            d.name for d in Department.objects.order_by("path") if d.depth == 1
        ]
        assert by_path != child_names

    def test_single_query(self, django_assert_num_queries):
        root = Department.objects.create(code="R", name="根")
        for i in range(5):
            Department.objects.create(code=f"C{i}", name=f"子{i}", parent=root)
        with django_assert_num_queries(1):
            build_tree_rows(Department.objects.all())
