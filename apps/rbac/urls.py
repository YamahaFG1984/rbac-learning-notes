from django.urls import path

from . import views

app_name = "rbac"

urlpatterns = [
    path("permissions/", views.permission_list, name="permission_list"),
    path("roles/", views.role_list, name="role_list"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<int:pk>/edit/", views.role_update, name="role_update"),
    path("roles/<int:pk>/delete/", views.role_delete, name="role_delete"),
    path("roles/<int:pk>/permissions/", views.role_perm_assign, name="role_perm_assign"),
]
