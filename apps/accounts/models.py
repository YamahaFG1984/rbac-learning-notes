from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import TreeModel


class Department(TreeModel):
    """部门（组织架构节点）。

    树的存储与遍历逻辑在 apps.common.models.TreeModel（ADR-003），
    v0.4.0 起与 Permission 共用。
    """

    code = models.CharField("部门编码", max_length=64, unique=True)
    name = models.CharField("部门名称", max_length=64)
    order_num = models.SmallIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta(TreeModel.Meta):
        verbose_name = "部门"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


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
