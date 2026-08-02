"""角色权限配置 / 数据范围 / 用户角色的 API（v1.3.0，SPA 管理页需要）。

这些接口只做翻译，判断全在 services.py 和 perm_tree.py 里——
所以这里的测试重点不是「功能对不对」，而是**规则有没有被抄第二遍**。
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.demo import DEMO_PASSWORD, build_demo_world
from apps.rbac.constants import DataScope
from apps.rbac.models import Permission, Role, RolePermission
from apps.rbac.services import get_role_permission_ids
from apps.tickets.permissions import TicketPerm


@pytest.fixture
def world(db):
    return build_demo_world()


def api_as(username):
    client = APIClient()
    resp = client.post(
        reverse("api:token_obtain_pair"),
        {"username": username, "password": DEMO_PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
    return client


def node_by_code(nodes, code):
    return next(n for n in nodes if n["code"] == code)


# --------------------------------------------------------------------------- #
# 🔴 本 tag 唯一的硬骨头
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestInheritedFlag:
    """`inherited` 的定义里那个 `and not is_direct` 是全部理由所在。

    disabled 的控件不会被提交（HTML checkbox 和 AntD Tree 都是）。
    一个权限如果既是直接授予、又是继承来的，一律禁用就会导致
    保存时把**直接授权静默删掉**——没有报错，用户过几天才发现。
    """

    def test_pure_inherited_is_disabled(self, world):
        """客服主管继承客服专员。专员的 create 对主管来说是纯继承。"""
        manager = Role.objects.get(code="cs_manager")
        nodes = api_as("superadmin").get(
            f"/api/v1/roles/{manager.pk}/permissions/"
        ).json()["nodes"]

        create = node_by_code(nodes, TicketPerm.CREATE)
        assert create["inherited"] is True, "纯继承项必须标为 inherited（界面禁用）"
        assert create["checked"] is True, "继承来的权限界面上要显示成勾选"

    def test_role_own_perm_is_not_inherited(self, world):
        """主管自己的 delete 不是继承来的。"""
        manager = Role.objects.get(code="cs_manager")
        nodes = api_as("superadmin").get(
            f"/api/v1/roles/{manager.pk}/permissions/"
        ).json()["nodes"]

        delete = node_by_code(nodes, TicketPerm.DELETE)
        assert delete["inherited"] is False
        assert delete["checked"] is True

    def test_both_direct_and_inherited_stays_checkable(self, world):
        """🔴 自测用例 5：一个权限**既直接授予又继承**时，必须**可勾选**。

        标成 inherited（=禁用）的话，AntD 的 Tree 不会把它放进 checkedKeys，
        保存时这条直接授权就被静默删除了。
        """
        manager = Role.objects.get(code="cs_manager")
        create_perm = Permission.objects.get(code=TicketPerm.CREATE)

        # 让 create 同时成为主管的**直接**权限（它本来就从专员继承）
        RolePermission.objects.create(role=manager, permission=create_perm)

        nodes = api_as("superadmin").get(
            f"/api/v1/roles/{manager.pk}/permissions/"
        ).json()["nodes"]
        create = node_by_code(nodes, TicketPerm.CREATE)

        assert create["checked"] is True
        assert create["inherited"] is False, (
            "既直接授予又继承的项不能标为 inherited —— "
            "禁用它会让保存时把直接授权静默删掉"
        )

    def test_saving_keeps_a_dual_granted_perm(self, world):
        """承上：把界面上「勾着的、非禁用的」项提交回去，直接授权还在。

        这条测试模拟的是前端真实的提交逻辑：
        只提交 checked 且 !inherited 的节点。
        """
        manager = Role.objects.get(code="cs_manager")
        create_perm = Permission.objects.get(code=TicketPerm.CREATE)
        RolePermission.objects.create(role=manager, permission=create_perm)

        client = api_as("superadmin")
        nodes = client.get(f"/api/v1/roles/{manager.pk}/permissions/").json()["nodes"]

        submitted = [n["id"] for n in nodes if n["checked"] and not n["inherited"]]
        assert create_perm.pk in submitted, "前端会提交它，因为它没被禁用"

        client.put(
            f"/api/v1/roles/{manager.pk}/permissions/",
            {"permissions": submitted},
            format="json",
        )
        assert create_perm.pk in get_role_permission_ids(manager)

    def test_catalog_nodes_are_never_inherited(self, world):
        """catalog 没有权限码（code=None），不参与继承判断。"""
        manager = Role.objects.get(code="cs_manager")
        nodes = api_as("superadmin").get(
            f"/api/v1/roles/{manager.pk}/permissions/"
        ).json()["nodes"]

        catalogs = [n for n in nodes if n["code"] is None]
        assert catalogs, "演示数据里应该有 catalog 节点"
        assert all(n["inherited"] is False for n in catalogs)


# --------------------------------------------------------------------------- #
# 权限不可放大（ADR-011）—— 服务端必须自己拦
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestPrivilegeEscalation:
    def test_cannot_grant_perms_you_lack(self, world):
        """🔴 前端的树只是界面，攻击者直接 PUT 一个 id 列表是几秒钟的事。"""
        sysadmin_role = Role.objects.get(code="sysadmin")
        # sysadmin 自己没有 ticket:ticket:delete
        delete_perm = Permission.objects.get(code=TicketPerm.DELETE)

        resp = api_as("sysadmin").put(
            f"/api/v1/roles/{sysadmin_role.pk}/permissions/",
            {"permissions": [delete_perm.pk]},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.json()["rejected"] >= 1, "越权的项要被拒，且要告诉调用方"
        assert delete_perm.pk not in get_role_permission_ids(sysadmin_role)

    def test_rejected_count_is_reported_not_silently_dropped(self, world):
        """静默丢弃会让管理员以为保存成功了。"""
        role = Role.objects.get(code="sysadmin")
        resp = api_as("sysadmin").put(
            f"/api/v1/roles/{role.pk}/permissions/",
            {"permissions": [Permission.objects.get(code=TicketPerm.DELETE).pk]},
            format="json",
        )
        assert set(resp.json()) == {"saved", "rejected"}

    def test_assign_perm_needs_its_own_permission(self, world):
        """cs_manager 连角色列表都看不到，更不能改权限。"""
        role = Role.objects.get(code="cs_manager")
        client = api_as("cs_manager")

        assert client.get(f"/api/v1/roles/{role.pk}/permissions/").status_code == 403
        assert (
            client.put(
                f"/api/v1/roles/{role.pk}/permissions/",
                {"permissions": []},
                format="json",
            ).status_code
            == 403
        )

    def test_cannot_grant_roles_you_lack(self, world):
        """把自己不具备的角色授予他人 —— 同样在服务端拦（ADR-011）。"""
        target = User.objects.get(username="no_role")
        manager_role = Role.objects.get(code="cs_manager")

        resp = api_as("sysadmin").put(
            f"/api/v1/users/{target.pk}/roles/",
            {"roles": [manager_role.pk]},
            format="json",
        )
        assert resp.json()["rejected"] >= 1
        assert not target.user_roles.filter(role=manager_role).exists()

    def test_grantable_flag_matches_can_grant_role(self, world):
        """界面上把「你授不出去的角色」标出来，判断走 can_grant_role。

        ⚠️ 前端不重算 —— 重算就是把 ADR-011 的规则抄第二遍。
        """
        target = User.objects.get(username="no_role")
        payload = api_as("sysadmin").get(f"/api/v1/users/{target.pk}/roles/").json()

        by_code = {r["code"]: r for r in payload["roles"]}
        assert by_code["cs_manager"]["grantable"] is False
        # 超管授得出任何角色
        payload = api_as("superadmin").get(f"/api/v1/users/{target.pk}/roles/").json()
        assert all(r["grantable"] for r in payload["roles"])


# --------------------------------------------------------------------------- #
# 数据范围
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDataScope:
    def test_returns_flat_tree_with_checked(self, world):
        role = Role.objects.get(code="cs_manager")
        payload = api_as("superadmin").get(
            f"/api/v1/roles/{role.pk}/data-scope/"
        ).json()

        assert payload["dataScope"] == DataScope.DEPT_AND_BELOW
        assert payload["customValue"] == DataScope.CUSTOM
        assert len(payload["departments"]) == 6

    def test_saving_does_not_expand_subtree(self, world):
        """🔴 只存用户勾了哪几个部门，**不展开子树**。

        展开后再存的话，将来新增的子部门永远进不了这个范围——
        而管理员勾「客服部」时的意图几乎肯定包含「以后新建的下级」。
        展开发生在查询时（get_role_custom_dept_ids）。
        """
        from apps.rbac.services import get_role_custom_dept_ids, get_role_department_ids

        role = Role.objects.get(code="cs_manager")
        cs = world["cs"]

        api_as("superadmin").put(
            f"/api/v1/roles/{role.pk}/data-scope/",
            {"dataScope": DataScope.CUSTOM, "departments": [cs.pk]},
            format="json",
        )

        # 存的是 1 个
        assert get_role_department_ids(role) == {cs.pk}
        # 查的时候才展开成 4 个（客服部 + 三个组）
        assert len(get_role_custom_dept_ids(role)) == 4

    def test_new_child_department_is_included_automatically(self, world):
        """承上，这才是「不提前展开」的收益。"""
        from apps.accounts.models import Department
        from apps.rbac.services import get_role_custom_dept_ids

        role = Role.objects.get(code="cs_manager")
        api_as("superadmin").put(
            f"/api/v1/roles/{role.pk}/data-scope/",
            {"dataScope": DataScope.CUSTOM, "departments": [world["cs"].pk]},
            format="json",
        )

        new_dept = Department.objects.create(
            code="CS4", name="客服四组", parent=world["cs"], order_num=40
        )
        assert new_dept.pk in get_role_custom_dept_ids(role)


# --------------------------------------------------------------------------- #
# 审计日志
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestAuditApi:
    def test_requires_audit_perm(self, world):
        assert api_as("cs_manager").get("/api/v1/audit-logs/").status_code == 403
        assert api_as("sysadmin").get("/api/v1/audit-logs/").status_code == 200

    def test_is_read_only_at_the_http_layer(self, world):
        """🔴 第三道防线：模型挡单对象、QuerySet 挡批量、这里挡 HTTP 入口。

        写成 ModelViewSet 的话 DELETE 会一路走到 QuerySet 才被拦，
        用户看到的是 500 而不是 405。
        """
        client = api_as("superadmin")
        assert client.post("/api/v1/audit-logs/", {}, format="json").status_code == 405

        role = Role.objects.get(code="cs_manager")
        client.put(
            f"/api/v1/roles/{role.pk}/data-scope/",
            {"dataScope": DataScope.DEPT_ONLY, "departments": []},
            format="json",
        )
        log_id = client.get("/api/v1/audit-logs/").json()["results"][0]["id"]

        assert client.delete(f"/api/v1/audit-logs/{log_id}/").status_code == 405
        assert client.patch(
            f"/api/v1/audit-logs/{log_id}/", {"action": "x"}, format="json"
        ).status_code == 405

    def test_detail_carries_added_and_removed(self, world):
        """审计日志要能回答「当时到底发生了什么」——detail 里得有可读的东西。"""
        client = api_as("superadmin")
        role = Role.objects.get(code="cs_manager")
        export_perm = Permission.objects.get(code=TicketPerm.EXPORT)

        client.put(
            f"/api/v1/roles/{role.pk}/permissions/",
            {"permissions": [export_perm.pk]},
            format="json",
        )

        logs = client.get("/api/v1/audit-logs/?action=role.perm_set").json()["results"]
        assert logs, "分配权限必须留下审计记录"
        assert "removed" in logs[0]["detail"] or "added" in logs[0]["detail"]


# --------------------------------------------------------------------------- #
# 树形接口不能分页（fe-v0.12.0 踩到的）
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestTreeEndpointsAreNotPaginated:
    """🔴 树不能分页。

    客户端拿第 1 页的 20 个节点去建树，第 21 个节点的父节点如果在第 2 页，
    整条分支就**悄无声息地消失**——不报错、不警告，只是少了几个。

    我在 fe-v0.12.0 真的踩了：前端传 ?page_size=500，
    但 DRF 没配 page_size_query_param，参数被静默忽略，
    权限点页只显示了 26 个里的 20 个。
    「传了一个不被识别的参数」是最难发现的一类错误：它长得像生效了。
    """

    def test_permissions_returns_everything(self, world):
        payload = api_as("superadmin").get("/api/v1/permissions/").json()
        assert isinstance(payload, list), "不能是 {count, results} 分页结构"
        assert len(payload) == Permission.objects.count() == 26

    def test_departments_returns_everything(self, world):
        payload = api_as("superadmin").get("/api/v1/departments/").json()
        assert isinstance(payload, list)
        assert len(payload) == 6

    def test_tree_stays_complete_past_the_default_page_size(self, world):
        """造 30 个部门 —— 超过 PAGE_SIZE=20，分页的话这里会掉一半。"""
        from apps.accounts.models import Department

        for i in range(30):
            Department.objects.create(
                code=f"T{i}", name=f"临时{i}", parent=world["hq"], order_num=i
            )

        payload = api_as("superadmin").get("/api/v1/departments/").json()
        assert len(payload) == 36

        # 每个非根节点的父节点都必须在结果里，否则前端建树时会丢分支
        ids = {d["id"] for d in payload}
        orphans = [d for d in payload if d["parent"] is not None and d["parent"] not in ids]
        assert orphans == []
