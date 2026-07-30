from django.db import models

from apps.common.models import TreeModel

from .constants import PermType


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
