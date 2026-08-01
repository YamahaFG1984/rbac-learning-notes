"""生产环境配置。

注意这里一律用 os.environ[...] 而不是 os.environ.get(..., default)：
缺配置就启动失败，好过带着默认密钥跑起来。
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

# 数据模型不使用任何数据库特有字段，切换 PostgreSQL 只需改这里（ADR-014、NFR-10）
if os.environ.get("DATABASE_URL", "").startswith("postgres"):
    import urllib.parse as _urlparse

    _u = _urlparse.urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _u.path.lstrip("/"),
            "USER": _u.username,
            "PASSWORD": _u.password,
            "HOST": _u.hostname,
            "PORT": _u.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
    }
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# 安全响应头
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
# ⚠️ 刻意设为 False，这不是安全倒退（F-ADR-004）。
#
# Django 的 CSRF 是 double-submit：cookie 一份、请求头一份，服务端比对。
# 模板渲染由 {% csrf_token %} 注入；SPA 没有服务端表单，只能自己从
# cookie 里读 csrftoken 放进 X-CSRFToken 头——httpOnly 会让它读不到，
# 于是 SPA 的所有写请求全部 403。
#
# 官方文档明确：CSRF_COOKIE_HTTPONLY **不提供任何实质防护**。
#   · CSRF token 本来就不是秘密，只需「攻击者的站点读不到」，
#     而同源策略已经保证了这一点
#   · httpOnly 防的是「XSS 偷走凭证」；但 XSS 已经在同源内，
#     它可以直接发请求，拿不拿得到 token 都一样
#
# 真正需要保护的 sessionid 仍然是 httpOnly（Django 默认行为）。
#
# 📌 v0.18.0 时我把它设成了 True，那是「照着安全清单抄」的产物——
#    我没想清楚它防的到底是什么。抄来的安全措施，和抄来的架构一样危险。
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
