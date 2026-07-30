"""权限管理模块自身的权限点声明。"""


class RolePerm:
    VIEW = "system:role:view"
    CREATE = "system:role:create"
    UPDATE = "system:role:update"
    DELETE = "system:role:delete"
    ASSIGN_PERM = "system:role:assign_perm"


class PermPerm:
    VIEW = "system:perm:view"


PERMISSIONS = [
    {
        "code": None,
        "name": "权限管理",
        "type": "catalog",
        "icon": "shield",
        "order": 20,
        "children": [
            {
                "code": RolePerm.VIEW,
                "name": "角色管理",
                "type": "menu",
                "url_name": "rbac:role_list",
                "icon": "user-group",
                "order": 10,
                "children": [
                    {"code": RolePerm.CREATE, "name": "新建角色", "type": "button", "order": 10},
                    {"code": RolePerm.UPDATE, "name": "编辑角色", "type": "button", "order": 20},
                    {"code": RolePerm.DELETE, "name": "删除角色", "type": "button", "order": 30},
                    {
                        "code": RolePerm.ASSIGN_PERM,
                        "name": "分配权限",
                        "type": "button",
                        "order": 40,
                    },
                ],
            },
            {
                "code": PermPerm.VIEW,
                "name": "权限点",
                "type": "menu",
                "url_name": "rbac:permission_list",
                "icon": "key",
                "order": 20,
                "children": [],
            },
        ],
    },
]
