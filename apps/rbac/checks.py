"""启动自检：找出未声明权限要求的视图。

装饰器方案（ADR-008）唯一的风险是「忘了加」，而忘了加的后果是接口裸奔。
既然风险已知，就必须有机制把它变成**启动期可见**的错误，
而不是等着线上被人发现。

    默认拒绝需要机制来保证，不能靠开发者的自觉。
    沉默不能被解释为同意——没有装饰器 = 配置错误，而不是 = 公开访问。
"""

from django.core.checks import Warning, register
from django.urls import URLPattern, URLResolver, get_resolver

# 这些前缀不归我们的权限体系管
IGNORED_PREFIXES = (
    "admin/",
    "static/",
    "media/",
    "__debug__/",
    # API 路由走 DRF 的 permission_classes 而不是我们的装饰器，
    # 由 rbac.W002 单独检查（v1.2.0）。
    "api/",
)


def _iter_views(resolver=None, prefix=""):
    resolver = resolver or get_resolver()
    for entry in resolver.url_patterns:
        route = prefix + str(entry.pattern)
        if isinstance(entry, URLResolver):
            yield from _iter_views(entry, route)
        elif isinstance(entry, URLPattern):
            yield route, entry.callback


def _unwrap(view):
    """穿透 Django 的层层包装，找到权限声明的载体。

    类视图：as_view() 返回闭包，带 view_class 属性 -> 取类
    函数视图：装饰器链用 functools.wraps 设置 __wrapped__ -> 沿它向内找
    """
    cls = getattr(view, "view_class", None)
    if cls is not None:
        return cls

    seen = set()
    current = view
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if hasattr(current, "_required_perm") or hasattr(current, "_required_any_perms"):
            return current
        if getattr(current, "_is_public", False):
            return current
        current = getattr(current, "__wrapped__", None)
    return view


def _has_declaration(target):
    return any(
        getattr(target, attr, None)
        for attr in (
            "_required_perm",
            "_required_any_perms",
            "required_perm",
            "required_any_perms",
        )
    ) or getattr(target, "_is_public", False)


@register()
def check_view_permissions(app_configs, **kwargs):
    """rbac.W001：视图未声明权限要求。"""
    problems = []
    for route, view in _iter_views():
        if route.startswith(IGNORED_PREFIXES):
            continue
        target = _unwrap(view)
        if _has_declaration(target):
            continue
        name = getattr(target, "__name__", repr(target))
        problems.append(
            Warning(
                f"视图 {name}（路由 /{route}）未声明权限要求。",
                hint=(
                    "用 @require_perm('app:resource:action') 声明所需权限，"
                    "或用 @public_view(reason='...') 显式声明公开访问。"
                    "沉默不能被解释为同意。"
                ),
                id="rbac.W001",
            )
        )
    return problems


@register()
def check_viewset_perm_maps(app_configs, **kwargs):
    """rbac.W002：ViewSet 的 perm_map 未覆盖它的全部 action。

    这是 rbac.W001 在 API 层的对应物。

    HasPerm 对漏配的 action 返回 403（默认拒绝），所以漏配不会造成
    安全漏洞——但会造成「接口莫名 403」的运维问题。启动时报出来，
    比等前端提工单强。

    ⚠️ 自定义 @action 是漏配的重灾区：它们不在标准 CRUD 列表里。
    """
    from django.urls import get_resolver

    problems = []
    seen = set()

    for _route, view in _iter_views():
        cls = getattr(view, "view_class", None) or getattr(view, "cls", None)
        if cls is None or not hasattr(cls, "get_extra_actions"):
            continue  # 不是 DRF ViewSet
        if cls in seen:
            continue
        seen.add(cls)

        perm_map = getattr(cls, "perm_map", None)
        if perm_map is None:
            problems.append(
                Warning(
                    f"ViewSet {cls.__name__} 未声明 perm_map。",
                    hint=(
                        "声明 perm_map = {action: 权限码}；"
                        "确实不需要权限管控的话，显式写 perm_map = {} 并注明理由。"
                    ),
                    id="rbac.W002",
                )
            )
            continue

        declared = set(perm_map)
        actual = set()
        for method_map in getattr(cls, "_actions_map", {}).values():
            actual.add(method_map)
        # 标准 CRUD action
        for name in ("list", "retrieve", "create", "update", "partial_update", "destroy"):
            if hasattr(cls, name):
                actual.add(name)
        # 自定义 @action
        for extra in cls.get_extra_actions():
            actual.add(extra.__name__)

        missing = actual - declared
        if missing:
            problems.append(
                Warning(
                    f"ViewSet {cls.__name__} 的 perm_map 未覆盖：{sorted(missing)}。",
                    hint="HasPerm 会对未覆盖的 action 返回 403（默认拒绝），"
                    "接口将无法使用。",
                    id="rbac.W002",
                )
            )

    return problems
