from django.urls import path

from . import views

app_name = "rbac"

urlpatterns = [
    path("permissions/", views.permission_list, name="permission_list"),
]
