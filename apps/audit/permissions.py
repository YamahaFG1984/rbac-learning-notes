"""审计日志的权限点声明。"""


class AuditPerm:
    VIEW = "system:audit:view"


PERMISSIONS = [
    {
        "code": None,
        "name": "系统监控",
        "type": "catalog",
        "icon": "chart",
        "order": 30,
        "children": [
            {
                "code": AuditPerm.VIEW,
                "name": "审计日志",
                "type": "menu",
                "url_name": "audit:log_list",
                "route_path": "/monitor/audit",
                "component": "monitor/AuditLogs",
                "icon": "Profile",
                "order": 10,
                "children": [],
            },
        ],
    },
]
