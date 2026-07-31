"""工单模块的权限点声明。"""


class TicketPerm:
    VIEW = "ticket:ticket:view"
    CREATE = "ticket:ticket:create"
    UPDATE = "ticket:ticket:update"
    DELETE = "ticket:ticket:delete"
    # 派单不是普通的编辑——它是把工作分配给别人。
    # 界面上有独立的按钮，就该有独立的权限点（ADR-004 的粒度原则）。
    ASSIGN = "ticket:ticket:assign"
    EXPORT = "ticket:ticket:export"


PERMISSIONS = [
    {
        "code": None,
        "name": "工单管理",
        "type": "catalog",
        "icon": "ticket",
        "order": 5,
        "children": [
            {
                "code": TicketPerm.VIEW,
                "name": "工单列表",
                "type": "menu",
                "url_name": "tickets:list",
                "icon": "list",
                "order": 10,
                "children": [
                    {"code": TicketPerm.CREATE, "name": "新建工单", "type": "button", "order": 10},
                    {"code": TicketPerm.UPDATE, "name": "编辑工单", "type": "button", "order": 20},
                    {"code": TicketPerm.DELETE, "name": "删除工单", "type": "button", "order": 30},
                    {"code": TicketPerm.ASSIGN, "name": "派单", "type": "button", "order": 40},
                    {"code": TicketPerm.EXPORT, "name": "导出工单", "type": "button", "order": 50},
                ],
            },
        ],
    },
]
