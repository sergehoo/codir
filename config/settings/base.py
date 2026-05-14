"""
Settings de base CODIR — Django 6 + DRF + Channels.
Tout est configurable par variables d'environnement (django-environ).
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(DJANGO_DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# ─── Security ──────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ─── Apps ──────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
    "drf_spectacular",
    "axes",
    "django_celery_beat",
    "django_celery_results",
    "storages",
]

# ─── Bêta : on n'active que le cœur fonctionnel + support ──────────
# Les apps full architecture (kpis, budgets, risks, analytics, ai_engine, …)
# restent dans le repo mais sont retirées d'INSTALLED_APPS pour ne pas
# migrer des tables non utilisées en bêta.
LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.governance",
    "apps.meetings",
    "apps.agendas",
    "apps.decisions",
    "apps.action_plans",
    "apps.documents",
    "apps.notifications",
    "apps.audit_logs",
    "apps.dashboards",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.tenant.TenantMiddleware",
    "core.middleware.audit.AuditMiddleware",
    "core.middleware.request_id.RequestIdMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ─── Templates ─────────────────────────────────────────────────────────
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
            ],
        },
    },
]

# ─── Auth ──────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Database ──────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="codir"),
        "USER": env("POSTGRES_USER", default="codir"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="codir"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── DRF ───────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "20/min", "user": "1000/min"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ─── JWT ───────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "HS256",  # RS256 en prod avec SIGNING_KEY = clé privée RSA
}

# ─── Channels ──────────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", default="redis://localhost:6379/0")]},
    },
}

# ─── Celery ────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_ROUTES = {
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.action_plans.tasks.*": {"queue": "default"},
    "apps.meetings.tasks.*": {"queue": "default"},
}

# ─── Celery Beat — tâches récurrentes bêta ──────────────────
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # ── Détection tâches en retard — chaque heure ──
    "detect-overdue-tasks": {
        "task": "apps.notifications.tasks.detect_overdue_tasks_task",
        "schedule": crontab(minute=0, hour="*"),
    },
    # ── Rappels meetings — toutes les 15 min ──
    "send-meeting-reminders": {
        "task": "apps.meetings.tasks.send_meeting_reminders",
        "schedule": crontab(minute="*/15"),
    },
    # ── Alertes échéances J+1/J+2 — 08h00 ──
    "send-due-soon-alerts": {
        "task": "apps.notifications.tasks.send_due_soon_alerts_task",
        "schedule": crontab(minute=0, hour=8),
    },
    # ── Rappels quotidiens utilisateur — 09h00 ──
    "send-daily-task-reminders-morning": {
        "task": "apps.notifications.tasks.send_daily_task_reminders_task",
        "schedule": crontab(minute=0, hour=9),
    },
    # ── Rappels quotidiens utilisateur — 16h00 ──
    "send-daily-task-reminders-afternoon": {
        "task": "apps.notifications.tasks.send_daily_task_reminders_task",
        "schedule": crontab(minute=0, hour=16),
    },
    # ── Résumé manager — 09h15 ──
    "send-manager-daily-summaries-morning": {
        "task": "apps.notifications.tasks.send_manager_daily_summaries_task",
        "schedule": crontab(minute=15, hour=9),
    },
    # ── Résumé manager — 16h15 ──
    "send-manager-daily-summaries-afternoon": {
        "task": "apps.notifications.tasks.send_manager_daily_summaries_task",
        "schedule": crontab(minute=15, hour=16),
    },
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = env("CELERY_TIMEZONE", default="Africa/Abidjan")

# ─── Email ─────────────────────────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CODIR Executive <no-reply@codir.local>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = 30

# URL frontend pour générer des liens absolus dans les emails
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")
DEFAULT_SITE_NAME = "CODIR Executive"

# ─── Cache ─────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
    },
}

# ─── Storage ───────────────────────────────────────────────────────────
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET", default="codir-dev"),
            "endpoint_url": env("S3_ENDPOINT", default="http://localhost:9000"),
            "access_key": env("S3_ACCESS_KEY", default=""),
            "secret_key": env("S3_SECRET_KEY", default=""),
            "region_name": env("S3_REGION", default="eu-west-1"),
            "default_acl": "private",
            "file_overwrite": False,
            "addressing_style": "path",
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ─── OpenSearch ────────────────────────────────────────────────────────
OPENSEARCH_URL = env("OPENSEARCH_URL", default="http://localhost:9200")

# ─── i18n ──────────────────────────────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ─── CORS ──────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True

# ─── drf-spectacular ───────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "CODIR API",
    "DESCRIPTION": "Executive Operating System — CODIR REST API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ─── Axes (anti brute-force) ───────────────────────────────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]

# ─── IA ────────────────────────────────────────────────────────────────
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
OLLAMA_URL = env("OLLAMA_URL", default="http://localhost:11434")
AI_DEFAULT_PROVIDER = env("AI_DEFAULT_PROVIDER", default="openai")

# ─── Logging ───────────────────────────────────────────────────────────
# JSON formatter optionnel : si python-json-logger n'est pas installé,
# on retombe gracieusement sur le formatter "verbose".
try:
    import pythonjsonlogger.jsonlogger  # noqa: F401
    _HAS_JSON_LOGGER = True
except ImportError:
    _HAS_JSON_LOGGER = False

_LOG_FORMATTERS = {
    "verbose": {
        "format": "[{asctime}] {levelname} {name}: {message}",
        "style": "{",
    },
}
if _HAS_JSON_LOGGER:
    _LOG_FORMATTERS["json"] = {
        "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
        "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
    }

_DEFAULT_FORMATTER = "verbose" if (DEBUG or not _HAS_JSON_LOGGER) else "json"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": _LOG_FORMATTERS,
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": _DEFAULT_FORMATTER},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ─── Sentry ────────────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
