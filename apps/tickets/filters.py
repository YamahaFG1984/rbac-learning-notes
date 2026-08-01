"""工单列表的筛选条件。

⚠️ 抽出来的理由和 export.py 一样：模板版和 API 版**必须筛得一模一样**。

   否则会出现一个很难查的现象——同一个用户在两个前端看到的条数不同，
   而两边的数据权限其实都是对的。

⚠️ 注意这里筛的是**业务条件**，不是权限。
   权限过滤由 .for_user() 完成，且必须已经在传进来的 queryset 上做过了。
   两者绝不能混在一个函数里：混在一起之后，
   任何人加一个业务筛选条件都可能顺手改坏权限过滤。
"""

from django.db.models import Q


def apply_ticket_filters(queryset, params):
    """params 是 request.GET / request.query_params（两者接口一致）。"""
    if kw := params.get("kw", "").strip():
        queryset = queryset.filter(Q(title__icontains=kw) | Q(content__icontains=kw))
    if status := params.get("status"):
        queryset = queryset.filter(status=status)
    if priority := params.get("priority"):
        queryset = queryset.filter(priority=priority)
    return queryset
