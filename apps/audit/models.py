from django.conf import settings
from django.db import models

from .constants import AuditAction, AuditResult


class AuditLogQuerySet(models.QuerySet):
    """审计日志只写不改不删（FR-9.4）。

    ⚠️ 模型的 save()/delete() 只挡得住单对象操作——
       AuditLog.objects.filter(...).delete() 走的是 QuerySet，不调用模型方法。
       所以这一层必须也拦住。
    """

    def update(self, **kwargs):
        raise RuntimeError("审计日志不可修改")

    def delete(self):
        raise RuntimeError("审计日志不可删除")


class AuditLog(models.Model):
    """审计日志。

    ⚠️ 已知简化（设计文档第 9 节第 5 条）：
       本表与业务数据同库。应用层的不可变保护只能防止「误操作」和
       「代码里的错误」，**防不住有数据库权限的恶意者**。

       真正的审计需要独立存储：日志系统（ELK/Loki）、只追加的表、
       或 WORM（一次写入多次读取）存储。审计数据和被审计的系统
       必须由不同的人控制。
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作者",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    # ⚠️ 冗余存一份用户名快照。actor 是 SET_NULL：用户被删除后 actor 变 null，
    #    没有这个字段你就不知道当初是谁操作的了。
    #    审计日志几乎所有字段都该是快照——它记录的是「当时的事实」，
    #    不该随当前状态变化（同 v0.13.0 工单部门快照的道理）。
    actor_name = models.CharField("操作者名", max_length=64, blank=True)
    action = models.CharField(
        "动作", max_length=64, choices=AuditAction.choices, db_index=True
    )
    target_type = models.CharField("目标类型", max_length=64, blank=True)
    target_id = models.CharField("目标ID", max_length=64, blank=True)
    target_repr = models.CharField("目标描述", max_length=128, blank=True)  # 同样是快照
    detail = models.JSONField("详情", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=256, blank=True)
    result = models.CharField(
        "结果", max_length=16, choices=AuditResult.choices, default=AuditResult.SUCCESS
    )
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.actor_name} {self.action}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("审计日志不可修改")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("审计日志不可删除")
