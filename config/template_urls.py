"""Django 模板版（阶段一）的路由。

⚠️ 从 fe-v0.1.0 起整体挂在 /django/ 前缀下，把根路径让给 React SPA。
   两套前端并存，共用同一个后端（F-ADR-001）。

   各 app 内部的 app_name 与 url_name 一个字都没改，
   所以模板里的 {% url %} 全部自动生效——这是当初坚持用 URL name
   而非硬编码路径的红利。
"""

from django.urls import include, path

urlpatterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("rbac/", include("apps.rbac.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("audit/", include("apps.audit.urls")),
]
