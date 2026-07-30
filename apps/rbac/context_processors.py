"""模板层的权限注入。

⚠️ 这里做的是**体验优化**，不是安全边界。

    隐藏按钮的用户，照样能删除——攻击者不点你的按钮，他直接发请求。
    真正的安全边界只有一个：服务端视图层的 @require_perm（v0.9.0）。

    每一个受权限控制的按钮，都必须有一个对应的服务端检查。
    成对出现，缺一不可。
"""

from .services import get_user_perm_codes


class LazyPermSet:
    """惰性权限集合：模板真的用到才解析，不用则零成本。

    登录页、错误页、静态页面完全不触发权限查询。
    """

    __slots__ = ("_user", "_codes")

    def __init__(self, user):
        self._user = user
        self._codes = None

    def _resolve(self):
        if self._codes is None:
            self._codes = get_user_perm_codes(self._user)
        return self._codes

    def __contains__(self, code):
        return code in self._resolve()

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self):
        return len(self._resolve())

    def __bool__(self):
        # 超管的 ALL_PERMS 哨兵 __len__ 是 0，但它绝不是「假」。
        # 不实现这个方法的话，模板里 {% if perms %} 会让超管走进 else 分支。
        return True

    def __repr__(self):
        state = "unresolved" if self._codes is None else f"{len(self._codes)} codes"
        return f"<LazyPermSet {state}>"


def rbac(request):
    # 不要在这里访问 request.user 的任何属性——那会触发 SimpleLazyObject 求值，
    # 把 user 从 session 里加载出来，惰性就白做了。
    return {"perms": LazyPermSet(getattr(request, "user", None))}
