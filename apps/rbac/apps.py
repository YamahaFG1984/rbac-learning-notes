from django.apps import AppConfig


class RbacConfig(AppConfig):
    name = "apps.rbac"
    verbose_name = "权限管理"

    def ready(self):
        # 必须 import，否则 @register() 不会执行，自检形同虚设
        from . import checks, signals  # noqa: F401
