from django.db import models


class Priority(models.IntegerChoices):
    LOW = 1, "低"
    MEDIUM = 2, "中"
    HIGH = 3, "高"


class Status(models.TextChoices):
    OPEN = "open", "待处理"
    PROCESSING = "processing", "处理中"
    CLOSED = "closed", "已关闭"
