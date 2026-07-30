from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel


class Department(TimestampedModel):
    """部门（组织架构节点）。

    存储方案：邻接表（parent 外键）+ 冗余的路径枚举字段 path。详见 ADR-003。

    path 格式为 /{根id}/{...}/{自身id}/，**首尾都有斜杠**。
    尾斜杠不是装饰，是正确性的关键：

        "/11/".startswith("/1")   -> True   部门 11 被误判为部门 1 的后代
        "/11/".startswith("/1/")  -> False  正确

    取子树因此只需一次查询，且能作为子查询下推到业务 SQL 里（NFR-2）：

        Department.objects.filter(path__startswith=dept.path)

    该查询天然包含自身（自身 path 就是前缀），正好符合「本部门及以下」的语义。
    """

    code = models.CharField("部门编码", max_length=64, unique=True)
    name = models.CharField("部门名称", max_length=64)
    parent = models.ForeignKey(
        "self",
        verbose_name="上级部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    # path / depth 是冗余数据，只在 save() 中维护，禁止手工赋值。
    # 不一致时用 `python manage.py rebuild_dept_path` 重建。
    path = models.CharField("路径", max_length=255, db_index=True, editable=False, default="")
    depth = models.SmallIntegerField("层级", default=0, editable=False)
    order_num = models.SmallIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "部门"
        verbose_name_plural = verbose_name
        # 按 path 字符串排序，天然就是树的先序遍历顺序
        ordering = ["path"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.parent_id and self.pk:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "部门不能以自己作为上级"})
            # 路径枚举的红利：一行判断即可挡住「移动到自己的后代下」
            if self.path and self.parent.path.startswith(self.path):
                raise ValidationError({"parent": "不能将部门移动到自己的下级部门中"})

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
            Department.objects.filter(pk=self.pk).update(path=new_path, depth=new_depth)
            self.path, self.depth = new_path, new_depth
            if old_path and old_path != new_path:
                self._cascade_subtree(old_path, new_path)

    def _cascade_subtree(self, old_path, new_path):
        """自身 path 变化后，同步更新所有后代的 path 与 depth。

        一次查询取出整棵子树，内存里做前缀替换，一次 bulk_update 写回。
        不用递归 save()：写操作次数从 O(n) 降到 O(1)。
        """
        descendants = list(
            Department.objects.filter(path__startswith=old_path).exclude(pk=self.pk)
        )
        if not descendants:
            return
        for node in descendants:
            node.path = new_path + node.path[len(old_path):]
            node.depth = node.path.count("/") - 2
        Department.objects.bulk_update(descendants, ["path", "depth"])

    def get_descendants(self, include_self=True):
        """本部门及其所有后代。一次查询，与树深度无关。"""
        qs = Department.objects.filter(path__startswith=self.path)
        return qs if include_self else qs.exclude(pk=self.pk)

    def get_ancestors(self, include_self=False):
        """从根到本部门的祖先链。"""
        ids = [int(x) for x in self.path.strip("/").split("/") if x]
        if not include_self:
            ids = ids[:-1]
        return Department.objects.filter(pk__in=ids)

    @property
    def is_leaf(self):
        return not self.children.exists()


class User(AbstractUser):
    """系统用户。

    继承 AbstractUser 而非 AbstractBaseUser：保留 Django 全套认证机制
    （UserManager、密码哈希、REQUIRED_FIELDS、PermissionsMixin），
    只增量添加业务字段。详见 ADR-002。

    两点约定，写在这里以免后人误用：

    1. 继承来的 `is_staff` 仅控制能否登录 Django admin，与本系统的
       RBAC 权限体系无关。业务代码不要使用它做权限判断。
    2. 继承来的 `first_name` / `last_name` 不符合中文姓名习惯，一律留空，
       用 `real_name`。删除继承字段的成本大于这点冗余，不折腾。

    超级管理员复用 Django 自带的 `is_superuser`，不新增 `is_superadmin`
    ——多一个语义重叠的字段，就多一处「两个字段不一致时听谁的」的 bug 温床。
    """

    real_name = models.CharField("姓名", max_length=32, blank=True)
    phone = models.CharField("手机号", max_length=20, blank=True)
    department = models.ForeignKey(
        Department,
        verbose_name="所属部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    last_login_ip = models.GenericIPAddressField("最后登录IP", null=True, blank=True)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return self.real_name or self.username
