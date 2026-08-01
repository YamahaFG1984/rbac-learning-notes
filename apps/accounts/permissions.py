"""组织管理模块的权限点声明。

权限码格式 app:resource:action（ADR-004），由 sync_permissions 命令同步入库。
在代码里声明的三个收益：可 grep、无 typo、进 code review。
"""


class DeptPerm:
    VIEW = "system:dept:view"
    CREATE = "system:dept:create"
    UPDATE = "system:dept:update"
    DELETE = "system:dept:delete"


class UserPerm:
    VIEW = "system:user:view"
    CREATE = "system:user:create"
    UPDATE = "system:user:update"
    DELETE = "system:user:delete"
    ASSIGN_ROLE = "system:user:assign_role"


PERMISSIONS = [
    {
        "code": None,
        "name": "组织管理",
        "type": "catalog",
        "icon": "building",
        "order": 10,
        "children": [
            {
                "code": DeptPerm.VIEW,
                "name": "部门管理",
                "type": "menu",
                "url_name": "accounts:department_list",
                "route_path": "/system/depts",
                "component": "system/Departments",
                "icon": "Sitemap",
                "order": 10,
                "children": [
                    {"code": DeptPerm.CREATE, "name": "新建部门", "type": "button", "order": 10},
                    {"code": DeptPerm.UPDATE, "name": "编辑部门", "type": "button", "order": 20},
                    {"code": DeptPerm.DELETE, "name": "删除部门", "type": "button", "order": 30},
                ],
            },
            {
                "code": UserPerm.VIEW,
                "name": "用户管理",
                "type": "menu",
                "url_name": "accounts:user_list",
                "route_path": "/system/users",
                "component": "system/Users",
                "icon": "Team",
                "order": 20,
                "children": [
                    {"code": UserPerm.CREATE, "name": "新建用户", "type": "button", "order": 10},
                    {"code": UserPerm.UPDATE, "name": "编辑用户", "type": "button", "order": 20},
                    {"code": UserPerm.DELETE, "name": "删除用户", "type": "button", "order": 30},
                    {
                        "code": UserPerm.ASSIGN_ROLE,
                        "name": "分配角色",
                        "type": "button",
                        "order": 40,
                    },
                ],
            },
        ],
    },
]
