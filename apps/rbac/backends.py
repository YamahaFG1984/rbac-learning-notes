"""把我们的权限接进 Django 的 user.has_perm()。

ADR-001：弃用 django.contrib.auth 的**授权**部分，但保留它的**认证**部分。
继承 ModelBackend 而不是 BaseBackend，是为了保留 authenticate()
和 get_user()（后者含 is_active 检查，见 v0.7.0 的纵深防御）。

接进 has_perm() 是低成本的兼容性投资：Django admin 和第三方代码继续可用。
"""

from django.contrib.auth.backends import ModelBackend

from .services import get_user_perm_codes, user_has_perm


class RBACBackend(ModelBackend):
    def has_perm(self, user_obj, perm, obj=None):
        return user_has_perm(user_obj, perm)

    def get_all_permissions(self, user_obj, obj=None):
        codes = get_user_perm_codes(user_obj)
        # 超管返回的是 ALL_PERMS 哨兵，它不可迭代成具体的码
        return set(codes)

    def get_group_permissions(self, user_obj, obj=None):
        # 我们不用 Django 的 Group
        return set()
