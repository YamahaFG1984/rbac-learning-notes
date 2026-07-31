import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_is_our_custom_model(self):
        """AUTH_USER_MODEL 指向我们的模型，而不是 auth.User。"""
        assert User.__module__ == "apps.accounts.models"
        assert User._meta.db_table == "accounts_user"

    def test_str_prefers_real_name(self):
        u = User(username="zhangsan", real_name="张三")
        assert str(u) == "张三"

    def test_str_falls_back_to_username(self):
        u = User(username="zhangsan", real_name="")
        assert str(u) == "zhangsan"

    def test_password_is_hashed(self):
        """NFR-6：密码必须哈希存储，不得明文。"""
        u = User.objects.create_user(username="u1", password="secret123")
        assert u.password != "secret123"
        assert "secret123" not in u.password
        assert "$" in u.password  # <algo>$<params>$<salt>$<hash>
        assert u.check_password("secret123")

    def test_production_uses_pbkdf2(self, settings):
        """⚠️ 测试配置把哈希器换成了 MD5，纯为提速（PBKDF2 每次约 100ms）。

        这类「为了跑得快而调整配置」的做法有个真实风险：
        **悄悄弱化了安全属性而没人发现**。

        所以单独断言一次：dev / prod 都不覆盖 PASSWORD_HASHERS，
        即沿用 Django 默认的 PBKDF2-SHA256（NFR-6）。
        """
        import os
        from importlib import import_module

        # prod 用 os.environ[...] 读密钥，缺了会直接崩——这正是它的设计意图
        os.environ.setdefault("DJANGO_SECRET_KEY", "test-only")
        os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "example.com")

        from config.settings import base, dev

        prod = import_module("config.settings.prod")

        for mod in (base, dev, prod):
            assert not hasattr(mod, "PASSWORD_HASHERS"), (
                f"{mod.__name__} 覆盖了 PASSWORD_HASHERS——只有 test 配置可以这么做"
            )

        # 用 Django 的默认值验证：不带任何覆盖时首选 PBKDF2
        settings.PASSWORD_HASHERS = [
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
        ]
        from django.contrib.auth.hashers import get_hasher

        assert get_hasher("default").algorithm == "pbkdf2_sha256"

    def test_superuser_flag(self):
        """超管复用 Django 自带的 is_superuser，不新增字段。"""
        su = User.objects.create_superuser(username="su", password="x")
        assert su.is_superuser is True
        assert not hasattr(su, "is_superadmin")
