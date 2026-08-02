"""SPA 需要的响应头。"""

from apps.rbac.cache import get_version


class RbacVersionMiddleware:
    """在 API 响应头里带上当前的 RBAC 全局版本号。

    🔴 它解决的问题在 Django 模板版**根本不存在**。

       模板版的界面和权限判断是同一次请求产生的：撤了权限，
       用户下一次点任何链接拿到的 HTML 里按钮就已经没了。

       SPA 手里是一份**快照**（登录时拉的 profile）。撤权之后：
         · 后端会拒绝他的删除请求（FR-4.5 承诺的是这个）
         · 但他屏幕上的删除按钮还在，点了才知道
       后端的承诺没有失效——它从来只管服务端。
       **这是 SPA 引入的新问题，不是后端的 bug。**

    ⚠️ 为什么是响应头而不是轮询 / WebSocket：
       版本号搭在**已有的**响应上，零额外请求；
       而且它的延迟正好等于后端的承诺（一次 API 请求）——
       前后端的生效语义因此对齐了，这比省几个请求更重要。

    ⚠️ 只给 /api/ 加。模板版的 HTML 每次都重算权限，
       给它加这个头没有意义，只是白白增加响应体积。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            # 一次 cache 读，不查库（复用 v0.16.0 已有的版本号，零额外存储）。
            #
            # ⚠️ 每个 API 响应都读一次。LocMem 无所谓，Redis 是一次网络往返，
            #    FileBasedCache 是一次磁盘读——高 QPS 下值得实测。
            #    这里不做请求级缓存：中间件本来就一个请求只走一次。
            response["X-RBAC-Version"] = str(get_version())
        return response
