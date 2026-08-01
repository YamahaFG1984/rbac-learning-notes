"""API 认证（F-ADR-003）。

SPA 走 **Session**（同域 + httpOnly Cookie + CSRF），
移动端 / 第三方 / 脚本走 **Bearer JWT**。两条通道并存。

为什么 SPA 不用 JWT——即使装进 httpOnly Cookie 也不用：

  1. JWT 的卖点是无状态，但 v1.1.0 已实测：simplejwt 每次请求都要查库
     取 user 并检查 is_active。**所谓无状态早就打了折。**
  2. 它的代价（签发出去在过期前无法撤销）是实打实的，而 v0.16.0 花了
     一整个 tag 保证「权限撤销后最迟下一次请求生效」——
     认证层给出一个撤不掉的凭证，与这个承诺自相矛盾。
  3. Session 白送三样：立即可撤销、CSRF 现成、禁用用户立即失效。

⚠️ 登录的业务规则（失败锁定、审计）全部复用 apps/accounts/auth_views.py
   的实现，一行都不重写——否则会出现「Web 登录被锁了，API 还能试」的漏洞。
"""

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token, rotate_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.auth_views import (
    LOGIN_FAILED_MESSAGE,
    LOGIN_LOCKED_MESSAGE,
    clear_login_failure,
    get_client_ip,
    is_locked_out,
    record_login_failure,
)
from apps.accounts.models import User
from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services import log as audit_log


def _request_meta(request):
    return {
        "ip": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """种下 csrftoken cookie。

    SPA 启动时先调它，之后所有写请求带 X-CSRFToken 头。

    ⚠️ 顺序不能反：登录本身也是 POST，也需要 CSRF token。
    """
    return Response({"detail": "ok", "csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = str(request.data.get("username", ""))
    password = str(request.data.get("password", ""))
    meta = _request_meta(request)

    if is_locked_out(username):
        from django.conf import settings

        minutes = settings.LOGIN_FAIL_LOCKOUT_SECONDS // 60
        return Response(
            {"detail": LOGIN_LOCKED_MESSAGE.format(minutes=minutes)},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        attempts = record_login_failure(username)
        audit_log(
            AuditAction.LOGIN_FAILED,
            detail={"username": username, "attempts": attempts, "channel": "api"},
            result=AuditResult.FAILURE,
            **meta,
        )
        # ⚠️ 400 而不是 401。
        #    401 会触发前端拦截器的「跳登录页」，而用户**已经在登录页**了——
        #    表现是页面莫名刷新一下，错误提示都来不及看（F-ADR-011）。
        return Response(
            {"detail": LOGIN_FAILED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST
        )

    clear_login_failure(username)
    login(request, user)  # 内部 cycle_key()，防会话固定
    # CSRF token 也要换：登录前拿到的 token 在登录后仍有效，
    # 是一个（较弱的）会话固定变体。
    rotate_token(request)
    User.objects.filter(pk=user.pk).update(last_login_ip=meta["ip"])
    audit_log(AuditAction.LOGIN, actor=user, detail={"channel": "api"}, **meta)

    from .views import build_profile_payload

    return Response(build_profile_payload(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    audit_log(
        AuditAction.LOGOUT,
        actor=request.user,
        detail={"channel": "api"},
        **_request_meta(request),
    )
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)
