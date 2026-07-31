"""认证：登录 / 登出。

认证（你是谁）不是授权（你能做什么）。Django 的认证做得很好，
我们不重写，只做业务增强（失败锁定、IP 记录）——见 ADR-001。
"""

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services import log as audit_log
from apps.rbac.decorators import public_view

from .forms import INPUT_CLS
from .models import User

# 统一文案：不区分「用户不存在」和「密码错误」（FR-5.2）。
# 分开提示等于给攻击者一个用户名枚举接口。
LOGIN_FAILED_MESSAGE = "用户名或密码错误"
LOGIN_LOCKED_MESSAGE = "登录失败次数过多，请 {minutes} 分钟后再试"


class LoginForm(forms.Form):
    username = forms.CharField(
        label="用户名",
        max_length=150,
        widget=forms.TextInput(attrs={"class": INPUT_CLS, "autofocus": True}),
    )
    password = forms.CharField(
        label="密码", widget=forms.PasswordInput(attrs={"class": INPUT_CLS})
    )


# --------------------------------------------------------------------------- #
# 登录失败计数
#
# 放 cache 而不是数据库或 session：
#   · 数据库 —— 每次失败都要写库，且用户不存在时无处可写
#   · session —— 攻击者换个 session 就绕过了，形同虚设
#   · cache   —— 有天然的 TTL（正好对应锁定时长），无需清理任务
# --------------------------------------------------------------------------- #


def _fail_key(username):
    return f"login_fail:{username}"


def record_login_failure(username):
    key = _fail_key(username)
    try:
        return cache.incr(key)
    except ValueError:  # key 不存在
        cache.set(key, 1, settings.LOGIN_FAIL_LOCKOUT_SECONDS)
        return 1


def clear_login_failure(username):
    cache.delete(_fail_key(username))


def is_locked_out(username) -> bool:
    return cache.get(_fail_key(username), 0) >= settings.LOGIN_FAIL_MAX_ATTEMPTS


def get_client_ip(request):
    """⚠️ X-Forwarded-For 是客户端可伪造的。

    只有在确信请求经过了可信反向代理（且代理会覆写这个头）时才能信任它。
    直接暴露在公网的应用不能信。
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _safe_redirect_target(request):
    """不校验 next 就是开放重定向漏洞：攻击者构造 ?next=https://evil.com，
    用户登录后被跳到钓鱼站，而且是从你的域名跳过去的。"""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return settings.LOGIN_REDIRECT_URL


@public_view(reason="登录页，未认证用户必须能访问")
def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]

        if is_locked_out(username):
            minutes = settings.LOGIN_FAIL_LOCKOUT_SECONDS // 60
            form.add_error(None, LOGIN_LOCKED_MESSAGE.format(minutes=minutes))
        else:
            user = authenticate(
                request, username=username, password=form.cleaned_data["password"]
            )
            if user is None:
                attempts = record_login_failure(username)
                audit_log(
                    AuditAction.LOGIN_FAILED,
                    detail={"username": username, "attempts": attempts},
                    ip=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    result=AuditResult.FAILURE,
                )
                form.add_error(None, LOGIN_FAILED_MESSAGE)
            else:
                clear_login_failure(username)
                # login() 内部会 cycle_key()，防会话固定攻击
                login(request, user)
                User.objects.filter(pk=user.pk).update(
                    last_login_ip=get_client_ip(request)
                )
                audit_log(
                    AuditAction.LOGIN,
                    actor=user,
                    ip=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                return redirect(_safe_redirect_target(request))

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@public_view(reason="登出，任何已登录用户都应能主动退出，不该额外要求权限")
@require_POST
def logout_view(request):
    """Django 5.x 起 LogoutView 只接受 POST。

    GET /logout/ 意味着攻击者可以在论坛发一张
    <img src="https://yoursite/logout/">，任何浏览到该页面的用户都会被强制登出。
    """
    audit_log(
        AuditAction.LOGOUT,
        actor=request.user,
        ip=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    logout(request)
    return redirect(reverse(settings.LOGOUT_REDIRECT_URL))
