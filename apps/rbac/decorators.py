"""Web 层的权限装饰器。

这是 ADR-013 说的「薄适配器」：把 HTTP 世界的东西翻译成内核认识的参数，
再把内核的返回值翻译回 HTTP 世界（PermissionDenied -> 403 页面）。
所有判断逻辑都在 services.user_has_perm() 里，这里一行都不重复实现。
"""

from functools import wraps

from django.core.exceptions import PermissionDenied

from .services import user_has_any_perm, user_has_perm


def require_perm(code: str):
    """要求当前用户拥有指定权限码，否则 403。

    权限声明写在视图旁边——代码即文档，改视图时不会忘记改权限。
    配合 rbac.W001 启动自检，保证没有视图被遗漏（ADR-008）。
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not user_has_perm(request.user, code):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        wrapper._required_perm = code
        return wrapper

    return decorator


def require_any_perm(*codes: str):
    """拥有任一权限即可通过。"""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not user_has_any_perm(request.user, codes):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        wrapper._required_any_perms = codes
        return wrapper

    return decorator


def public_view(reason: str):
    """显式声明本视图无需权限。

    ⚠️ reason 是**必填**参数，没有默认值。

    「这个接口不需要权限」是一个安全决策，安全决策必须留下依据。
    三个月后有人看到这行，能立刻知道当初为什么这么定，
    而不是猜「是有意的还是忘了加」。

    给 reason 一个默认值，这个标记就退化成了纯粹的「消警告」开关。
    """

    def decorator(view_func):
        view_func._is_public = True
        view_func._public_reason = reason
        return view_func

    return decorator
