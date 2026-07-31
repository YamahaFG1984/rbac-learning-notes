from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = "login", "登录"
    LOGIN_FAILED = "login_failed", "登录失败"
    LOGOUT = "logout", "登出"
    PERM_DENIED = "perm_denied", "访问被拒绝"
    ROLE_CREATE = "role.create", "创建角色"
    ROLE_UPDATE = "role.update", "修改角色"
    ROLE_DELETE = "role.delete", "删除角色"
    ROLE_PERM_SET = "role.perm_set", "分配角色权限"
    ROLE_SCOPE_SET = "role.scope_set", "设置数据范围"
    USER_ROLE_SET = "user.role_set", "分配用户角色"
    USER_CREATE = "user.create", "创建用户"
    USER_UPDATE = "user.update", "修改用户"
    USER_DELETE = "user.delete", "删除用户"


class AuditResult(models.TextChoices):
    SUCCESS = "success", "成功"
    FAILURE = "failure", "失败"
