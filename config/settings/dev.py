"""开发环境配置。"""

from .base import *  # noqa: F401,F403

DEBUG = True

SECRET_KEY = "django-insecure-dev-only-do-not-use-in-production"

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# ⚠️ 用文件缓存而不是 LocMemCache —— 理由是**跨进程失效**。
#
# LocMemCache 是**每个进程一份**。开发时至少有两类进程在动权限数据：
#   · runserver 提供服务
#   · manage.py sync_permissions / seed_demo / shell 改数据
#
# 管理命令里的 bump_version() 只 incr 了它自己进程内的版本号，
# runserver 那份完全不知道 —— 于是服务端继续用**变更前**的权限缓存，
# 最长 30 分钟（RBAC_CACHE_TTL）。
#
# 我在 fe-v0.12.0 被这个坑了：E2E 用 seed_demo --flush 重置数据后，
# cs_manager 登录进去菜单是空的、页面是 403，而数据库里角色明明是对的。
# 症状看起来像权限逻辑坏了，实际是缓存没跨进程。
#
# 生产用 Redis（见 prod.py），本来就是共享的。
# 让开发环境也共享，是为了**让开发环境的行为和生产一致**——
# 一个只在开发环境出现的诡异行为，会把人引向完全错误的排查方向。
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".cache",  # noqa: F405
    }
}
