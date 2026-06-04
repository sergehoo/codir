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
# Toujours autoriser localhost/127.0.0.1 — utilisé par le healthcheck Docker
# (curl http://localhost:8000/health/) même quand DJANGO_ALLOWED_HOSTS ne liste
# que le domaine public. Pas un risque de sécurité car non exposé via Traefik.
for _h in ("localhost", "127.0.0.1"):
    if _h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_h)
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
    "apps.meeting_recordings",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────
# Whitenoise DOIT être juste après SecurityMiddleware pour servir /static/
# (admin Django, DRF browsable API, etc.). Sans lui, gunicorn 404 sur /static/.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
    # ⚠ NE PAS utiliser CursorPagination par défaut : sa propriété par défaut
    # `ordering = "-created"` plante sur tous les modèles dont le champ est
    # `created_at` → FieldError 500. PageNumberPagination est compatible avec
    # `?page=N&page_size=M` que le frontend utilise déjà.
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
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
# Durées configurables via env pour pouvoir ajuster sans rebuild.
# CODIR est une app interne B2B avec MFA TOTP en place côté accounts ;
# on privilégie le confort utilisateur — sessions longues acceptables.
_JWT_ACCESS_HOURS = env.int("JWT_ACCESS_HOURS", default=24)
_JWT_REFRESH_DAYS = env.int("JWT_REFRESH_DAYS", default=30)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=_JWT_ACCESS_HOURS),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_JWT_REFRESH_DAYS),
    # Rotation désactivée : évite les race conditions sur appels concurrents
    # (2 onglets, refresh simultané → un des deux refresh part en blacklist).
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
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
    # Recordings : queue dédiée — pipeline lourd (audio I/O + API externes).
    "apps.meeting_recordings.tasks.*": {"queue": "recordings"},
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
    # ── Synthèse hebdomadaire utilisateur — vendredi 09h00 ──
    # Email avec toutes les tâches NON-TERMINÉES groupées par échéance.
    # CELERY_TIMEZONE = Africa/Abidjan → 9h locale Abidjan.
    "send-weekly-user-task-digest": {
        "task": "apps.notifications.tasks.send_weekly_user_task_digest_task",
        "schedule": crontab(minute=0, hour=9, day_of_week="fri"),
    },
    # ── EPI Score snapshot quotidien — 06h00 (avant tous les autres) ──
    "snapshot-epi-score-daily": {
        "task": "apps.dashboards.tasks.snapshot_epi_score_daily",
        "schedule": crontab(minute=0, hour=6),
    },
    # ── Génération des Meetings récurrents — 02h00 (avant tout) ──
    "generate-recurring-meetings": {
        "task": "apps.meetings.tasks.generate_recurring_meetings",
        "schedule": crontab(minute=0, hour=2),
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
# Adresse humaine à laquelle les destinataires peuvent répondre (différente
# de DEFAULT_FROM_EMAIL pour pouvoir conserver un From `noreply@...`).
EMAIL_REPLY_TO = env("EMAIL_REPLY_TO", default="")
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

# ─── Storage S3/MinIO ──────────────────────────────────────────────────
# Deux endpoints distincts :
# - S3_ENDPOINT          → URL interne (Django ↔ MinIO via réseau Docker)
# - S3_PUBLIC_ENDPOINT   → URL publique HTTPS (URLs présignées envoyées au
#                          navigateur). En dev = même valeur. En prod =
#                          https://storage.codir.datarium-dev.com (Traefik).
#
# `addressing_style=path` est OBLIGATOIRE pour MinIO (qui ne supporte pas
# le virtual-hosted style par défaut). AWS S3 supporte les deux, donc ça
# marche dans tous les cas.
#
# `signature_version=s3v4` requis par MinIO pour les URLs présignées valides.
_S3_COMMON_OPTIONS = {
    "endpoint_url": env("S3_ENDPOINT", default="http://codirminio:9000"),
    "access_key": env("S3_ACCESS_KEY", default=""),
    "secret_key": env("S3_SECRET_KEY", default=""),
    "region_name": env("S3_REGION", default="eu-west-1"),
    "default_acl": "private",
    "file_overwrite": False,
    "addressing_style": "path",
    "signature_version": "s3v4",
    # Custom domain : si défini, les URLs publiques sont générées avec ce
    # host (utile pour servir via Traefik avec un domaine HTTPS).
    "custom_domain": env("S3_PUBLIC_DOMAIN", default=""),
    "url_protocol": env("S3_URL_PROTOCOL", default="https:"),
    # Durée des URLs présignées (audio des recordings, docs PV, etc.).
    # 1h par défaut — assez pour ouvrir une session de lecture sans
    # régénérer trop souvent côté UI.
    "querystring_expire": env.int("S3_PRESIGN_EXPIRE", default=3600),
}

STORAGES = {
    # Bucket par défaut : documents, exports PDF, PV, avatars, etc.
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON_OPTIONS,
            "bucket_name": env("S3_BUCKET", default="codir-dev"),
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    # Bucket dédié aux enregistrements de réunions. Séparé pour permettre
    # une politique de rétention différente (RECORDING_RAW_RETENTION_DAYS),
    # des quotas IAM distincts, et un nettoyage indépendant.
    # Pour l'utiliser : `MeetingRecording.audio_file.storage = recordings_storage`
    # (déjà géré transparent via STORAGES défaut en bêta).
    "recordings": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON_OPTIONS,
            "bucket_name": env("RECORDING_S3_BUCKET", default="codir-recordings-dev"),
        },
    },
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

# Media (utilisé en fallback uniquement si le storage S3 par défaut échoue —
# ex: en dev sans MinIO, ou lors d'une coupure S3 transitoire en prod).
#
# ⚠️ IMPORTANT : en prod le container Django tourne avec `read_only: true`
# (sécurité Docker). Seuls les volumes explicitement montés sont writable.
# Le docker-compose monte le volume `codir_media` sur `/var/www/media:rw` →
# c'est LE seul endroit où Django peut écrire en fallback.
#
# Le défaut `/var/www/media` est compatible :
# - Prod Docker (volume monté à cet emplacement, owner=app:app)
# - Dev local : créer le dossier OU surcharger via env MEDIA_ROOT
MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default="/var/www/media")

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

# ─── Meeting recordings — transcription + LLM ──────────────────────────
# AssemblyAI : transcription + diarisation cloud (clé requise en prod).
ASSEMBLYAI_API_KEY = env("ASSEMBLYAI_API_KEY", default="")
ASSEMBLYAI_LANGUAGE = env("ASSEMBLYAI_LANGUAGE", default="fr")
# Modèle ASR AssemblyAI.
# DÉFAUT = VIDE → on ne passe PAS le paramètre au SDK, AssemblyAI utilise
# son meilleur modèle par défaut côté serveur (universal-2 en 2026, FR OK).
# C'est le mode le plus résilient car l'API AssemblyAI déprécie régulièrement
# les anciens noms de modèles (best → universal → universal-2 → universal-3-pro).
# Pour forcer un modèle : ASSEMBLYAI_MODEL=universal-2 (ou slam-1, nano, etc.)
# IMPORTANT : nécessite que la version du SDK assemblyai installée le supporte.
ASSEMBLYAI_MODEL = env("ASSEMBLYAI_MODEL", default="")
# Claude primary, DeepSeek fallback (compat OpenAI SDK).
RECORDING_AI_PRIMARY = env("RECORDING_AI_PRIMARY", default="anthropic")
RECORDING_AI_FALLBACK = env("RECORDING_AI_FALLBACK", default="deepseek")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-4-5-20250929")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
DEEPSEEK_BASE_URL = env("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-chat")
# Bucket dédié recordings (séparé du bucket documents pour quota + IAM).
RECORDING_S3_BUCKET = env("RECORDING_S3_BUCKET", default="codir-recordings-dev")
# Limite upload : 4h x 256 kbps Opus webm ≈ 460 Mo. On laisse 600 Mo de marge.
MAX_RECORDING_UPLOAD_MB = env.int("MAX_RECORDING_UPLOAD_MB", default=600)
# Durée d'extrait audio par speaker (en secondes) — sample d'identification UI.
SPEAKER_SAMPLE_DURATION_SEC = env.int("SPEAKER_SAMPLE_DURATION_SEC", default=8)
# Rétention audio brut (jours). 0 = pas de purge auto.
RECORDING_RAW_RETENTION_DAYS = env.int("RECORDING_RAW_RETENTION_DAYS", default=90)

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
