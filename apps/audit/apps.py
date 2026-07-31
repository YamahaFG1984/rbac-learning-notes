from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "apps.audit"
    verbose_name = "审计日志"

    def ready(self):
        from . import receivers  # noqa: F401
