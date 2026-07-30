from django.urls import path

from . import auth_views, views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.login_view, name="login"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("departments/", views.department_list, name="department_list"),
    path("departments/create/", views.department_create, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_update, name="department_update"),
    path("departments/<int:pk>/delete/", views.department_delete, name="department_delete"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_update, name="user_update"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/roles/", views.user_role_assign, name="user_role_assign"),
]
