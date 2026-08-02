"""角色数据范围的保存。

⚠️ 抽出来的理由和 apps/tickets/filters.py 一样：**两个前端必须做同一件事**。

   这里那件「同一件事」尤其重要——它包含**发出审计信号**。
   模板版和 API 版各写一遍的话，很可能只有一边记了日志，
   而缺失的那一边正好是攻击者会用的那一边。
"""

from apps.rbac.services import (
    get_role_department_ids,
    save_role_departments,
)
from apps.rbac.signals import role_scope_changed


def save_role_scope(role, data_scope, department_ids, actor=None):
    """更新角色的数据范围与自定义部门，并发出审计信号。

    ⚠️ department_ids **原样存**，不在这里展开子树。
       get_role_custom_dept_ids() 在查询时才展开——这样将来新增的子部门
       会自动包含进来，而管理员勾「客服部」时的意图几乎肯定包含
       「以后新建的下级」。提前展开的话，新部门永远进不来。

    ⚠️ 先取 before 再改，否则记录下来的「变更前」就是变更后。
       审计日志要能回答「当时到底发生了什么」，
       只说「有人动过」的日志三个月后毫无价值。
    """
    before_scope = role.data_scope
    before_depts = sorted(get_role_department_ids(role))

    role.data_scope = int(data_scope)
    role.save(update_fields=["data_scope", "updated_at"])
    save_role_departments(role, department_ids)

    after_depts = sorted(get_role_department_ids(role))

    role_scope_changed.send(
        sender=role.__class__,
        role=role,
        actor=actor,
        before={"data_scope": before_scope, "departments": before_depts},
        after={"data_scope": role.data_scope, "departments": after_depts},
    )
    return role
