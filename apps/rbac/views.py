from django.shortcuts import render

from apps.common.views import build_tree_rows

from .models import Permission


def permission_list(request):
    rows = build_tree_rows(Permission.objects.select_related("parent").all())
    return render(request, "rbac/permission_list.html", {"rows": rows})
