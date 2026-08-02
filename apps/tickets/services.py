"""工单域的业务查询。

⚠️ 本模块可以 import apps.rbac —— 依赖方向是 tickets → rbac → accounts → common。
   反过来（rbac import tickets）才是必须拒绝的。
"""

from apps.accounts.models import User
from apps.rbac.services import get_user_dept_ids


def get_assignable_users(actor):
    """`actor` 派单时可以选的处理人。

    📌 **这个函数是补一个漏洞补出来的。**

    v0.15.0 的 `TicketAssignForm` 用的是 ModelForm 的默认 queryset，
    也就是**全部用户**。于是：

        cs_manager 有 ticket:ticket:assign，没有 system:user:view，
        但派单下拉框里能看到公司全部 6 个人（含超管和技术部同事）。

    一个「不该看到用户列表」的人，通过另一个功能的下拉框看到了用户列表。
    权限点画得再细，也挡不住这种**从旁边绕过去**的泄露——
    这类漏洞不出现在权限矩阵里，因为矩阵测的是接口，而它藏在一个表单控件里。

    ⚠️ 范围规则用 get_user_dept_ids()（ADR-016），不在这里另写一套
       `Department.objects.filter(path__startswith=...)`。
       另写一套的那一刻，就有了两份迟早会不一致的部门树规则。

    ⚠️ 超管要特判，理由和 build_scope_q 里那句 `if user.is_superuser: return None`
       一样：超管的 department 可能是 None，而 get_user_dept_ids 对无部门用户
       返回**空集**（默认拒绝 4）。不特判的话，一个没配部门的超管会
       一个候选人都选不到——默认拒绝的方向是对的，但超管本就不该走这条路。
    """
    if actor.is_superuser:
        return User.objects.filter(is_active=True).select_related("department")

    return User.objects.filter(
        is_active=True,
        department_id__in=get_user_dept_ids(actor),
    ).select_related("department")
