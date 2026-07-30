from django.db import models


class DataScope(models.IntegerChoices):
    """角色的数据范围（ADR-007）。

    ⚠️ 编号刻意**从大范围到小范围递增**——这让「哪个范围更宽」变成一次整数比较，
       min(scopes) 就是最宽的那个。v0.14.0 用它做短路优化。

    但注意：合并多角色的数据范围时**不能**简单「取最宽枚举」，
    那样在 CUSTOM 参与时会丢数据。编号顺序只用于短路，不用于合并。
    """

    ALL = 1, "全部数据"
    DEPT_AND_BELOW = 2, "本部门及以下"
    DEPT_ONLY = 3, "仅本部门"
    SELF_ONLY = 4, "仅本人"
    CUSTOM = 5, "自定义部门"


class PermType(models.TextChoices):
    """权限点的三种节点类型。菜单与权限点合并为一张表，详见 ADR-005。

    catalog 纯分组容器，无权限码，不可点击
    menu    对应一个页面，有权限码 + 路由 + 图标
    button  对应页面内一个操作，只有权限码
    """

    CATALOG = "catalog", "目录"
    MENU = "menu", "菜单"
    BUTTON = "button", "按钮"


# 权限码 action 受控词表（ADR-004）。需要新动词时先在设计文档里加，再用。
ALLOWED_ACTIONS = frozenset(
    {
        "view",
        "create",
        "update",
        "delete",
        "export",
        "import",
        "assign",
        "assign_perm",
        "assign_role",
        "audit",
    }
)

# app:resource:action，全小写，词内下划线
PERM_CODE_PATTERN = r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$"
