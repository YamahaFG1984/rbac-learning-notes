from django.conf import settings
from django.db import models

from apps.accounts.models import Department
from apps.common.managers import DataScopedQuerySet
from apps.common.models import TimestampedModel

from .constants import Priority, Status


class Ticket(TimestampedModel):
    """工单。

    选工单作为业务示例，是因为它天然具备「创建人 / 处理人 / 归属部门」
    三个维度，恰好能演示数据权限的各种情形。

    v0.14.0 起接入数据权限：只需声明 ScopeConfig 三行 + 换一个 Manager，
    业务代码的其余部分完全不用动（FR-7.6）。
    """

    class ScopeConfig:
        """数据范围的归属字段声明（ADR-007）。

        build_scope_q() 读这个配置生成 Q 对象。接入成本 = 3 行。

        可选的 extra_q(user) 钩子是通往 ABAC 的门，但只开一条缝。
        """

        owner_field = "creator"  # SELF_ONLY 用它
        dept_field = "department"  # 各种部门范围用它


    title = models.CharField("标题", max_length=128)
    content = models.TextField("内容", blank=True)
    priority = models.SmallIntegerField(
        "优先级", choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        "状态", max_length=16, choices=Status.choices, default=Status.OPEN
    )
    # PROTECT：创建人是历史事实，删了用户就丢了这个事实。
    # 强制先处理工单（或者干脆只允许禁用用户，不允许删除）。
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )
    # SET_NULL：处理人是当前状态，人走了工单变成「无人认领」是合理的。
    # on_delete 的选择本质上是在回答「这个关系断了之后，剩下的数据还有意义吗」。
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    # ⚠️ 这是**快照**，不是实时取 creator.department。
    #
    # 如果不存这个字段而在查询时用 creator.department，那么创建人转岗后，
    # 他以前创建的所有工单会跟着他一起换部门——原部门主管突然看不到历史工单，
    # 新部门主管莫名其妙看到一堆不相干的。而且这个变化是**静默**的。
    #
    # 判断依据：这个值变化时，历史记录该不该跟着变？
    # 同类例子：订单里的商品价格必须快照，不能引用商品表的当前价格。
    department = models.ForeignKey(
        Department,
        verbose_name="归属部门",
        on_delete=models.PROTECT,
        related_name="tickets",
    )

    objects = DataScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "工单"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
