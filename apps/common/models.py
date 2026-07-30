"""公共抽象基类。"""

from django.core.exceptions import ValidationError
from django.db import models


class TimestampedModel(models.Model):
    """带创建/更新时间戳的抽象基类。

    abstract = True 是必须的——否则 Django 会为它建一张真实的表。
    """

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class TreeModel(TimestampedModel):
    """邻接表 + 冗余路径字段的树形抽象基类。详见 ADR-003。

    path 格式为 /{根id}/{...}/{自身id}/，**首尾都有斜杠**。
    尾斜杠不是装饰，是正确性的关键：

        "/11/".startswith("/1")   -> True   节点 11 被误判为节点 1 的后代
        "/11/".startswith("/1/")  -> False  正确

    取子树因此只需一次查询，且能作为子查询下推到业务 SQL 里（NFR-2）：

        Model.objects.filter(path__startswith=node.path)

    该查询天然包含自身（自身 path 就是前缀）。

    本基类由 Department（v0.3.0）与 Permission（v0.4.0）共用。
    """

    parent = models.ForeignKey(
        "self",
        verbose_name="上级",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    # path / depth 是冗余数据，只在 save() 中维护，禁止手工赋值。
    path = models.CharField("路径", max_length=255, db_index=True, editable=False, default="")
    depth = models.SmallIntegerField("层级", default=0, editable=False)

    class Meta:
        abstract = True
        # ⚠️ path 是**字符串**，字符串排序 ≠ 先序遍历。ID 跨到两位数就会错：
        #       "/2/6/10/" < "/2/6/7/"   因为 '1' < '7'
        #    所以 ordering 只用来保证结果稳定，不承担「树序」职责。
        #    真正的先序遍历 + order_num 排序由 common.views.build_tree_rows 在内存里做。
        ordering = ["path"]

    def clean(self):
        super().clean()
        if self.parent_id and self.pk:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "不能以自己作为上级"})
            # 路径枚举的红利：一行判断即可挡住「移动到自己的后代下」
            if self.path and self.parent.path.startswith(self.path):
                raise ValidationError({"parent": "不能移动到自己的下级中"})

    def save(self, *args, **kwargs):
        old_path = self.path
        # 新建时 pk 由数据库生成，path 里需要它 —— 只能先存再算。
        # 代价是新建多一次 UPDATE；换取的是不依赖数据库序列，保持可移植（ADR-014）。
        super().save(*args, **kwargs)

        parent_path = self.parent.path if self.parent_id else "/"
        new_path = f"{parent_path}{self.pk}/"
        new_depth = (self.parent.depth + 1) if self.parent_id else 0

        if new_path != self.path or new_depth != self.depth:
            # 直接打数据库，不能用 self.save() —— 会无限递归
            self.__class__.objects.filter(pk=self.pk).update(path=new_path, depth=new_depth)
            self.path, self.depth = new_path, new_depth
            if old_path and old_path != new_path:
                self._cascade_subtree(old_path, new_path)

    def _cascade_subtree(self, old_path, new_path):
        """自身 path 变化后，同步更新所有后代的 path 与 depth。

        一次查询取出整棵子树，内存里做前缀替换，一次 bulk_update 写回。
        不用递归 save()：写操作次数从 O(n) 降到 O(1)。
        """
        model = self.__class__
        descendants = list(model.objects.filter(path__startswith=old_path).exclude(pk=self.pk))
        if not descendants:
            return
        for node in descendants:
            node.path = new_path + node.path[len(old_path):]
            node.depth = node.path.count("/") - 2
        model.objects.bulk_update(descendants, ["path", "depth"])

    def get_descendants(self, include_self=True):
        """本节点及其所有后代。一次查询，与树深度无关。"""
        qs = self.__class__.objects.filter(path__startswith=self.path)
        return qs if include_self else qs.exclude(pk=self.pk)

    def get_ancestors(self, include_self=False):
        """从根到本节点的祖先链。"""
        ids = [int(x) for x in self.path.strip("/").split("/") if x]
        if not include_self:
            ids = ids[:-1]
        return self.__class__.objects.filter(pk__in=ids)

    @property
    def is_leaf(self):
        return not self.children.exists()
