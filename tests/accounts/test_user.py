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
        """NFR-6：密码使用 PBKDF2 哈希存储，不得明文。"""
        u = User.objects.create_user(username="u1", password="secret123")
        assert u.password != "secret123"
        assert u.password.startswith("pbkdf2_sha256$")
        assert u.check_password("secret123")

    def test_superuser_flag(self):
        """超管复用 Django 自带的 is_superuser，不新增字段。"""
        su = User.objects.create_superuser(username="su", password="x")
        assert su.is_superuser is True
        assert not hasattr(su, "is_superadmin")
