"""全局测试夹具。"""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_rbac_cache():
    """v0.16.0 起必须逐测试清缓存。

    不清的话，测试 A 的权限结果会被测试 B 读到，出现「单独跑绿、一起跑红」
    的诡异现象——权限系统的测试特别容易踩这个坑。
    """
    cache.clear()
    yield
    cache.clear()
