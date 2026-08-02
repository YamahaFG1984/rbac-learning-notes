"""API 异常处理。

⚠️ 本文件的存在源于一个 DRF 的行为细节，它直接影响 F-ADR-011：

    未认证请求本应返回 **401**，但加上 SessionAuthentication 之后变成了 **403**。

原因在 rest_framework/views.py 的 handle_exception()：

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        auth_header = self.get_authenticate_header(self.request)
        if auth_header:
            exc.auth_header = auth_header
        else:
            exc.status_code = status.HTTP_403_FORBIDDEN   # ← 降级

`get_authenticate_header()` 取的是**第一个**认证类的 `authenticate_header()`。
`JWTAuthentication` 返回 `Bearer realm="api"`，而 `SessionAuthentication`
返回 `None`——于是 401 被降级成了 403。

**这对 SPA 是致命的**：F-ADR-011 要求前端严格区分

    401 → 会话过期，跳登录页
    403 → 已登录但无权限，**绝不跳登录页**（否则死循环）

如果未认证也返回 403，前端只能看到 403，用户会永远停在「权限不足」的提示上，
而真实原因是他根本没登录。

两种修法：
  a. 把 JWTAuthentication 排在第一位 —— 能拿回 401，但等于告诉浏览器客户端
     「请使用 Bearer 认证」，语义是错的，而且依赖认证类的**顺序**这种脆弱前提。
  b. 显式处理（本文件）—— 直接表达我们要的语义。

选 b。顺序是实现细节，语义才是契约。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 判据必须是**异常类型**，不是「用户是否已认证」。

第一版我写的是「403 且 request.user 未认证 → 改成 401」，看起来很自然，
但它会误伤 **CSRF 失败**：

    SessionAuthentication.enforce_csrf() 校验失败时抛 PermissionDenied，
    此时认证流程被打断，request.user 是 AnonymousUser
    → 被误判成「未认证」→ 返回 401
    → 前端跳登录页，而用户**明明已经登录了**，只是 CSRF token 过期

正确的判据是：**DRF 降级的只有 NotAuthenticated 这一种异常**，
我们只把这一种改回来，其余的 403 原样保留。

    NotAuthenticated / AuthenticationFailed → 401（没登录 / 凭证无效）
    PermissionDenied（含 CSRF 失败）        → 403（已登录，但这个操作不行）
"""

from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler

# DRF 在没有 WWW-Authenticate 头时会把这两种异常降级成 403，我们改回来。
_UNAUTHENTICATED_EXCEPTIONS = (
    exceptions.NotAuthenticated,
    exceptions.AuthenticationFailed,
)


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if response.status_code == status.HTTP_403_FORBIDDEN and isinstance(
        exc, _UNAUTHENTICATED_EXCEPTIONS
    ):
        response.status_code = status.HTTP_401_UNAUTHORIZED

    return response
