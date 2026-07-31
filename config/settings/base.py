"""公共配置。

分层策略（ADR-014 的邻居）：base 放所有环境共有的内容，
dev / prod 各自 `from .base import *` 后覆盖差异项。

选多文件继承而非「单文件 + if DEBUG」，是因为后者让 `DEBUG = True`
这行代码存在于生产配置里——不可能出错，优于小心不要出错。
"""

from pathlib import Path

# config/settings/base.py -> config/settings -> config -> 仓库根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

# 顺序按依赖方向排列：tickets/audit -> rbac -> accounts -> common
LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.rbac",
    "apps.tickets",
    "apps.audit",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ⚠️ 必须在项目第一次 migrate 之前设定。一旦 auth 应用的迁移跑过，
#    再换用户模型会遇到几乎无解的外键依赖问题（ADR-002）。
AUTH_USER_MODEL = "accounts.User"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # 注入惰性的 perms 对象，模板里可写 {% if 'a:b:c' in perms %}
                # ⚠️ 这是体验优化，不是安全边界（ADR-012）
                "apps.rbac.context_processors.rbac",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# --------------------------------------------------------------------------- #
# 认证与会话（v0.7.0）
# --------------------------------------------------------------------------- #

AUTHENTICATION_BACKENDS = [
    # 故意只留我们的 backend，移除 ModelBackend：
    # 两套权限体系并存只会造成混淆（ADR-001）。
    # RBACBackend 继承自 ModelBackend，authenticate() 与 get_user()
    # （含 is_active 检查）都保留了。
    "apps.rbac.backends.RBACBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/accounts/departments/"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = 7200  # 2 小时
# 滑动过期：有操作就续期。代价是每个请求都写一次 session 存储
# ——用数据库存 session 时这是真实的写压力，生产环境通常改用 Redis。
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# RBAC
# 深度限制不只是防死循环——5 层以上的角色继承链，人已经无法在脑内推演了。
# 这条限制是在保护**可运维性**，不只是保护程序。
RBAC_MAX_ROLE_DEPTH = 5
RBAC_CACHE_TTL = 1800  # 30 分钟
RBAC_VERSION_KEY = "rbac:version"

# 登录失败锁定（FR-5.3）
LOGIN_FAIL_MAX_ATTEMPTS = 5
LOGIN_FAIL_LOCKOUT_SECONDS = 900  # 15 分钟


# --------------------------------------------------------------------------- #
# API（v1.1.0）
#
# API 与 Web 模板**并存**，不是替换。同一套业务逻辑、同一套权限内核，
# 服务两种完全不同的表现层——这是验证 ADR-013 解耦是否成功的唯一方法。
# --------------------------------------------------------------------------- #

from datetime import timedelta  # noqa: E402

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # ⚠️ v1.1.0：只有认证，没有授权。任何登录用户都能调所有接口。
    #    这是刻意留下的中间态，v1.2.0 换成 HasPerm。
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SIMPLE_JWT = {
    # 缩短 access 有效期是 JWT「签发出去无法撤销」的主要缓解手段——
    # 风险窗口 = 有效期
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}
