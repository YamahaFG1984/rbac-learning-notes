from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, TreeModel

from .constants import DataScope, PermType


class Permission(TreeModel):
    """权限点。

    菜单与权限点合并为一张表（ADR-005）：管理员的心智模型是
    「勾选这个角色能看到和能做的东西」，一棵树配一次，而不是维护
    两棵树和它们的映射关系。

    代价是本表混进了展示层字段（url_name / icon / is_visible）。
    我们接受这个污染——权限系统的用户是管理员而非架构师，
    领域纯洁性和管理便利性冲突时，选后者。

    权限点由代码声明（各 app 的 permissions.py）+ sync_permissions 命令同步，
    禁止手工往数据库塞：能自助添加权限点，就意味着可以添加一个代码里
    根本不检查的权限码，制造「配了但不生效」的静默失败。
    """

    # catalog 类型无权限码。多行 NULL 不违反 unique（SQL 标准：NULL != NULL），
    # 但不能用空串代替 NULL——空串是确定的值，第二个 catalog 就会撞唯一约束。
    code = models.CharField(
        "权限码", max_length=128, unique=True, null=True, blank=True
    )
    name = models.CharField("名称", max_length=64)
    perm_type = models.CharField(
        "类型", max_length=16, choices=PermType.choices, default=PermType.MENU
    )
    order_num = models.SmallIntegerField("排序", default=0)

    # --- 以下为展示层关注点（ADR-005）。若将来要拆表，边界在这里 ---
    url_name = models.CharField("URL name", max_length=128, blank=True)
    icon = models.CharField("图标", max_length=64, blank=True)
    is_visible = models.BooleanField("菜单可见", default=True)
    # --- 展示层字段结束 ---

    is_active = models.BooleanField("启用", default=True)
    # 代码中已移除但保留记录：物理删除会连带删掉 RolePermission 的历史授权，
    # 而历史授权的可解释性是有价值的（FR-2.6）
    is_deprecated = models.BooleanField("已废弃", default=False)

    class Meta(TreeModel.Meta):
        verbose_name = "权限点"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name}({self.code})" if self.code else self.name


class Role(TimestampedModel):
    """角色：一组权限的命名集合。

    v0.5.0 只做 RBAC0 的角色；继承（inherits_from）在 v0.12.0 加入，
    刻意分开是为了让 RBAC0 -> RBAC1 的 diff 干净。
    """

    code = models.CharField("角色编码", max_length=64, unique=True)
    name = models.CharField("角色名称", max_length=64)
    description = models.TextField("描述", blank=True)
    # ⚠️ 字段名刻意不叫 parent。
    #
    # 「父角色」在权限领域有两种相反的用法，会导致完全相反的实现。
    # inherits_from 只有一种读法，语义固定为 **child ⊇ parent**：
    # 「客服主管」的 inherits_from 是「客服专员」，主管拥有专员的全部权限。
    inherits_from = models.ForeignKey(
        "self",
        verbose_name="继承自",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inheritors",
        help_text="本角色将自动拥有所选角色的全部权限",
    )
    # 默认取最窄的 SELF_ONLY 而非 ALL：默认值必须指向「出错时后果最轻」的方向。
    # 忘配数据范围 -> 看得太少（有人报障，会被修好）
    #             -> 看得太多（没有任何人会报障）
    # 安全问题的特征就是「出错时没有反馈信号」。
    # ⚠️ 本字段 v0.14.0 才真正生效。
    data_scope = models.SmallIntegerField(
        "数据范围", choices=DataScope.choices, default=DataScope.SELF_ONLY
    )
    order_num = models.SmallIntegerField("排序", default=0)
    is_builtin = models.BooleanField("内置角色", default=False, help_text="内置角色不可删除")
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "角色"
        verbose_name_plural = verbose_name
        ordering = ["order_num", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.inherits_from_id:
            return
        if self.pk and self.inherits_from_id == self.pk:
            raise ValidationError({"inherits_from": "角色不能继承自己"})

        seen = {self.pk}
        current = self.inherits_from
        depth = 0
        while current is not None:
            if current.pk in seen:
                raise ValidationError({"inherits_from": "检测到角色继承环"})
            depth += 1
            if depth >= settings.RBAC_MAX_ROLE_DEPTH:
                raise ValidationError(
                    {
                        "inherits_from": f"角色继承深度不得超过 {settings.RBAC_MAX_ROLE_DEPTH} 层"
                    }
                )
            seen.add(current.pk)
            current = current.inherits_from

    def save(self, *args, **kwargs):
        # ModelForm.is_valid() 会自动调 full_clean()，但 Model.save() 不会。
        # 在 shell / 管理命令 / 数据迁移里直接 save()，环检测就不触发了。
        # 代价是每次保存多一轮校验；收益是任何路径都挡得住。
        self.full_clean(exclude=None, validate_unique=False)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 视图层也会拦一道，但 shell / 管理命令 / admin 都能绕过视图。
        # 模型层这道用于兜住那些路径（对比 Department 用 on_delete=PROTECT
        # ——那是更强的数据库级约束，可惜「内置」是业务语义，DB 表达不了）。
        if self.is_builtin:
            raise RuntimeError(f"内置角色「{self.name}」不可删除")
        return super().delete(*args, **kwargs)


class RolePermission(models.Model):
    """角色-权限绑定。

    只存**直接授予**的权限。继承来的权限在运行时计算（v0.12.0），不落库。

    为什么不物化继承结果？物化让查询快一次，代价是父角色权限变更时要重算
    所有后代角色的物化数据——一旦漏了或失败，就出现「数据库里的权限和规则
    不一致」，而且这种不一致是**静默**的，没人会发现。
    """

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )

    class Meta:
        verbose_name = "角色权限"
        verbose_name_plural = verbose_name
        unique_together = [("role", "permission")]

    def __str__(self):
        return f"{self.role} -> {self.permission}"


class UserRole(models.Model):
    """用户-角色绑定。

    一个用户可以有多个角色，权限取**并集**（FR-4.1）——现实中一个人身兼两职，
    自然是两份职责的权限都有，而不是只有交集那部分。

    granted_by / granted_at 本 tag 只存不用，是给 v0.17.0 审计日志准备的。
    """

    # 用 settings.AUTH_USER_MODEL 字符串引用，不直接 import User，避免循环导入
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="授权人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="granted_roles",
    )
    granted_at = models.DateTimeField("授权时间", auto_now_add=True)

    class Meta:
        verbose_name = "用户角色"
        verbose_name_plural = verbose_name
        unique_together = [("user", "role")]

    def __str__(self):
        return f"{self.user} -> {self.role}"
