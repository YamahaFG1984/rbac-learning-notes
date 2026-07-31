"""数据权限的 QuerySet 注入。"""

from django.core.exceptions import ImproperlyConfigured
from django.db import models


class DataScopedQuerySet(models.QuerySet):
    def for_user(self, user):
        """按用户的数据范围过滤。

        ⚠️ 必须**显式**调用。本项目坚决不做隐式 / thread-local 自动过滤（ADR-009）：

          · Celery 任务、管理命令、定时脚本里没有 request，thread-local 是空的。
            返回全集（危险）还是空集（任务全挂）？两个答案都不对。
          · 测试里没有 request，要么每个测试都 mock，要么测的不是生产路径。
          · Django 5.2 的 async view 中同一线程可能服务多个并发请求，
            thread-local 会串。
          · 最根本的：它让「这个查询有没有被过滤」变得**不可见**。
            读到 Ticket.objects.all() 时，你无法判断它返回什么。

        显式优于隐式——这条 Python 之禅在安全代码里不是风格偏好，是硬要求。
        你应该能通过 grep 找出所有绕过数据权限的查询。

        代价是「可能忘记调用」。我们不假装这个代价不存在，
        而是用 Mixin + 测试缓解它：**可观测的风险优于隐形的保证**。
        """
        from apps.rbac.services import build_scope_q

        cfg = getattr(self.model, "ScopeConfig", None)
        if cfg is None:
            # 配置错误要在第一次调用时立刻炸掉，而不是静默返回全集
            raise ImproperlyConfigured(
                f"{self.model.__name__} 使用了 DataScopedQuerySet 但未定义 ScopeConfig"
            )
        q = build_scope_q(user, cfg)
        return self if q is None else self.filter(q)
