from django.db import models


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
