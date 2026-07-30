"""全局错误页。

handler4xx/5xx 必须写在**根** urls.py 里，且值是字符串路径不是函数对象。
"""

from django.shortcuts import render


def custom_403(request, exception=None):
    return render(request, "403.html", status=403)


def custom_404(request, exception=None):
    return render(request, "404.html", status=404)


def custom_500(request):
    # 不传 context——500 时请求上下文可能已损坏
    return render(request, "500.html", status=500)
