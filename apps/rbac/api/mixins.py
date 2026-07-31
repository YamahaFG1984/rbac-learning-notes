"""API 层的数据权限。"""


class ScopedQuerysetMixin:
    """数据范围过滤。

    DRF 的 get_object() 内部走 get_queryset()，所以重写这一处
    就同时保护了 list / retrieve / update / partial_update / destroy
    ——不会出现「只挡住列表」或「只挡住 GET」的疏漏。

    范围外的记录由 DRF 的 get_object() 抛 Http404，正好符合我们的要求
    （范围外返回 404 而非 403，避免泄露存在性）。
    """

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)
