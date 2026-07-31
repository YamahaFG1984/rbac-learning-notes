"""测试专用配置。

只改「与被测行为无关但拖慢速度」的项——**绝不改变任何权限逻辑**，
否则测的就不是生产路径了。
"""

from .dev import *  # noqa: F401,F403

# PBKDF2 故意设计得慢（100 万次迭代 ≈ 100ms/次），这在生产是对的：
# 它让离线暴力破解变得昂贵。但测试里每建一个用户就付 100ms，
# 几百个用户下来就是几十秒。
#
# 换成 MD5 只影响「哈希算得多快」，不影响「密码是否被哈希」——
# 密码存储的正确性由 tests/accounts/test_user.py 的
# test_password_is_hashed 单独守着（它断言 pbkdf2_sha256 前缀，
# 因此该用例仍需在 dev 配置下才有意义，见其内部说明）。
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
