"""公共抽象基类。"""

from django.db import models


class TimestampedModel(models.Model):
    """带创建/更新时间戳的抽象基类。

    abstract = True 是必须的——否则 Django 会为它建一张真实的表。
    """

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
