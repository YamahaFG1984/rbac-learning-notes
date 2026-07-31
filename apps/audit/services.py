"""审计日志写入。"""

import logging

from .constants import AuditResult
from .models import AuditLog

logger = logging.getLogger(__name__)


def log(
    action,
    *,
    actor=None,
    target=None,
    detail=None,
    ip=None,
    user_agent="",
    result=AuditResult.SUCCESS,
):
    """写一条审计日志。

    ⚠️ 记录失败不影响主流程——审计不该让用户的正常操作挂掉。

       这是有争议的：在高合规要求的场景（金融），「审计写不进去就不许操作」
       才是对的。本项目选前者，因为教学系统的可用性优先。
    """
    try:
        is_real_user = actor is not None and getattr(actor, "is_authenticated", False)
        return AuditLog.objects.create(
            actor=actor if is_real_user else None,
            actor_name=(getattr(actor, "username", "") or "-") if actor else "-",
            action=action,
            target_type=target.__class__.__name__ if target is not None else "",
            target_id=str(getattr(target, "pk", "")) if target is not None else "",
            target_repr=str(target)[:128] if target is not None else "",
            detail=detail or {},
            ip=ip,
            user_agent=(user_agent or "")[:256],
            result=result,
        )
    except Exception:  # noqa: BLE001
        logger.exception("审计日志写入失败: action=%s", action)
        return None
