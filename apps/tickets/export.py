"""工单导出。

⚠️ 抽成独立模块，是因为**导出是最容易被忽略的越权入口**：
   它通常是后加的功能，代码路径和列表页不同，很容易忘记过滤。

   v1.2.0 加 API 层时这个风险变成了现实——模板版和 API 版各有一个导出入口。
   两份 CSV 代码 = 两个可能漂移的地方，其中一个改了过滤条件另一个不知道。

   所以：**一份 CSV 写法，两个入口共用；数据来源都必须是调用方传进来的
   已经 .for_user() 过的 queryset。**
"""

import csv

from django.http import HttpResponse

HEADER = [
    "ID",
    "标题",
    "状态",
    "优先级",
    "创建人",
    "归属部门",
    "处理人",
    "创建时间",
]


def tickets_csv_response(queryset) -> HttpResponse:
    """把已经过数据权限过滤的 queryset 写成 CSV 响应。

    ⚠️ 本函数**不做**任何权限过滤——它拿到什么就写什么。
       这是刻意的：过滤的唯一执行点是调用方的 .for_user()。
       如果这里也过滤一次，就有了两个执行点，而其中一个迟早会被改错。

    验收标准：导出的行数 == 列表页显示的总数。
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="tickets.csv"'
    writer = csv.writer(response)
    writer.writerow(HEADER)
    for t in queryset.iterator():
        writer.writerow(
            [
                t.id,
                t.title,
                t.get_status_display(),
                t.get_priority_display(),
                str(t.creator),
                t.department.name,
                str(t.assignee) if t.assignee else "",
                t.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return response
