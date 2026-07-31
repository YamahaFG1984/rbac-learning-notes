from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("rbac/", include("apps.rbac.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("audit/", include("apps.audit.urls")),
]

handler403 = "config.views.custom_403"
handler404 = "config.views.custom_404"
handler500 = "config.views.custom_500"
