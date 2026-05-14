# 03 — Architecture backend (Django)

## 1. Stack technique précise

| Composant | Version | Rôle |
|---|---|---|
| Python | 3.12 | Runtime |
| Django | 6.0 | Framework principal |
| Django REST Framework | 3.15 | API REST |
| Django Channels | 4.x | ASGI / WebSockets |
| Daphne / Uvicorn | dernière | Serveur ASGI |
| Gunicorn | 22.x | Serveur WSGI (HTTP sync) |
| PostgreSQL | 16 | OLTP principale |
| pgvector | 0.7 | Embeddings RAG |
| Redis | 7 | Cache + Celery broker + Channels layer |
| Celery | 5.4 | Tâches asynchrones |
| Celery Beat | — | Tâches planifiées |
| OpenSearch | 2.x | Recherche full-text + analytics |
| MinIO / S3 | — | Stockage objets (documents, exports) |
| djangorestframework-simplejwt | 5.x | JWT |
| django-cors-headers | 4.x | CORS |
| django-axes | 6.x | Anti brute force |
| django-allauth + dj-rest-auth | dernière | SSO (Google, Microsoft, SAML via custom backend) |
| drf-spectacular | 0.27 | OpenAPI 3 |
| django-storages | 1.14 | Backend MinIO/S3 |
| pgcrypto | natif PG | Chiffrement champs sensibles |
| psycopg | 3.x | Driver PostgreSQL async-ready |

## 2. Structure du projet backend

```
backend/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pyproject.toml                      ← config ruff, mypy, pytest
├── config/
│   ├── __init__.py
│   ├── asgi.py                         ← entry ASGI (HTTP + WS)
│   ├── wsgi.py                         ← entry WSGI (fallback)
│   ├── urls.py                         ← router racine
│   ├── routing.py                      ← Channels routing
│   ├── celery.py                       ← app Celery
│   └── settings/
│       ├── __init__.py
│       ├── base.py                     ← config commune
│       ├── dev.py                      ← override dev
│       ├── prod.py                     ← override prod
│       └── test.py                     ← override tests
├── apps/                               ← 23 apps métier
│   ├── __init__.py
│   ├── accounts/
│   ├── organizations/
│   ├── governance/
│   ├── codir/
│   ├── meetings/
│   ├── agendas/
│   ├── decisions/
│   ├── action_plans/
│   ├── workflows/
│   ├── dashboards/
│   ├── kpis/
│   ├── budgets/
│   ├── risks/
│   ├── reports/
│   ├── analytics/
│   ├── ai_engine/
│   ├── realtime/
│   ├── notifications/
│   ├── documents/
│   ├── search/
│   ├── integrations/
│   ├── audit_logs/
│   ├── mobile_api/
│   └── administration/
└── core/                               ← code transverse (pas une app Django)
    ├── middleware/                     ← TenantMiddleware, AuditMiddleware
    ├── permissions/                    ← RBAC, ABAC
    ├── pagination/
    ├── exceptions/
    ├── mixins/
    ├── utils/
    └── tests/                          ← fixtures, factories partagées
```

## 3. Anatomie d'une app Django CODIR

Chaque app suit la même structure interne, pour qu'un développeur retrouve ses repères :

```
apps/decisions/
├── __init__.py
├── apps.py                   ← AppConfig, ready() pour signals
├── models.py                 ← Modèles
├── managers.py               ← TenantManager + custom QuerySets
├── serializers.py            ← DRF serializers
├── views.py                  ← ViewSets DRF
├── urls.py                   ← Router DRF
├── permissions.py            ← Permissions DRF spécifiques
├── services.py               ← Logique métier (appelable hors HTTP)
├── selectors.py              ← Requêtes lecture complexes
├── tasks.py                  ← Tâches Celery
├── signals.py                ← Signaux (post_save, etc.)
├── consumers.py              ← Channels consumers (si WS)
├── filters.py                ← django-filter
├── admin.py                  ← Django admin custom
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_api.py
│   └── factories.py
└── migrations/
```

La séparation **views / services / selectors** est inspirée de [HackSoft Django Styleguide]. Les views font HTTP, les services écrivent, les selectors lisent. Cela rend les tests rapides et la logique réutilisable depuis Celery / shell / management commands.

## 4. Configuration centrale (`config/settings/base.py` — extraits commentés)

```python
# config/settings/base.py
from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# ─── Sécurité ───────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ─── Apps ───────────────────────────────────────────────────────
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
    "rest_framework.authtoken",
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
LOCAL_APPS = [
    "apps.accounts",
    "apps.organizations",
    "apps.governance",
    "apps.codir",
    "apps.meetings",
    "apps.agendas",
    "apps.decisions",
    "apps.action_plans",
    "apps.workflows",
    "apps.dashboards",
    "apps.kpis",
    "apps.budgets",
    "apps.risks",
    "apps.reports",
    "apps.analytics",
    "apps.ai_engine",
    "apps.realtime",
    "apps.notifications",
    "apps.documents",
    "apps.search",
    "apps.integrations",
    "apps.audit_logs",
    "apps.mobile_api",
    "apps.administration",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware (ordre critique) ────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.tenant.TenantMiddleware",        # custom
    "core.middleware.audit.AuditMiddleware",          # custom
    "core.middleware.request_id.RequestIdMiddleware", # custom
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ─── Auth ───────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.backends.MultiFactorBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ─── DB ─────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres:///codir"),
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["OPTIONS"] = {"sslmode": env.str("PG_SSLMODE", "prefer")}

# ─── DRF ────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "core.permissions.tenant.IsTenantMember",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CursorPagination",
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
    "EXCEPTION_HANDLER": "core.exceptions.handlers.api_exception_handler",
}

# ─── JWT ────────────────────────────────────────────────────────
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "RS256",
    "SIGNING_KEY": env.str("JWT_PRIVATE_KEY"),
    "VERIFYING_KEY": env.str("JWT_PUBLIC_KEY"),
}

# ─── Channels ───────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL")]},
    },
}

# ─── Celery ─────────────────────────────────────────────────────
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_ROUTES = {
    "apps.ai_engine.tasks.*": {"queue": "ai"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.reports.tasks.*": {"queue": "reports"},
    "apps.integrations.tasks.*": {"queue": "integrations"},
    "*": {"queue": "default"},
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ─── Cache ──────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    },
}

# ─── Storage ────────────────────────────────────────────────────
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET"),
            "endpoint_url": env("S3_ENDPOINT"),
            "access_key": env("S3_ACCESS_KEY"),
            "secret_key": env("S3_SECRET_KEY"),
            "default_acl": "private",
            "file_overwrite": False,
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ─── i18n ───────────────────────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# ─── Logging structuré JSON ─────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

## 5. Authentification, JWT, MFA, SSO

CODIR ne gère pas d'authentification triviale. Les exigences en font une brique critique.

**Mots de passe.** Hashage Argon2 (paramétré pour 250 ms de calcul), longueur min 12, dictionnaires interdits, rotation forcée tous les 90 jours pour les rôles exécutifs. `django-axes` bloque l'IP et le compte après 5 échecs avec captcha progressif.

**JWT.** Algorithme RS256 (asymétrique), access token 15 min, refresh token 7 jours en cookie HttpOnly Secure SameSite=Strict, rotation à chaque usage, blacklist côté serveur via `simplejwt.token_blacklist`. Les claims incluent `org_id`, `roles`, `mfa_passed`, `session_id`.

**MFA.** Implémentation à 3 facteurs au choix : TOTP (Google Authenticator / Authy, RFC 6238), WebAuthn (clés physiques YubiKey, FIDO2, biométrie OS), notification push mobile (Flutter app reçoit prompt, valide par biométrie). Le MFA est obligatoire pour les rôles DG, DAF, Audit, SuperAdmin.

**SSO.** Trois protocoles supportés en parallèle : OAuth2 / OIDC (Google Workspace, Microsoft Entra ID via Azure AD, Okta, Keycloak), SAML 2.0 (ADFS legacy, partenaires custom), LDAP / Active Directory (déploiement on-prem). Le SSO peut être imposé au niveau organisation (`organizations.Organization.sso_enforced=True`), désactivant alors les mots de passe locaux.

**Sessions et géolocalisation.** Chaque login crée un `accounts.Session` avec IP, user-agent, géolocalisation MaxMind, device fingerprint. L'utilisateur voit ses sessions actives et peut les révoquer. Anomalie de géolocalisation → MFA forcé + alerte email.

## 6. RBAC + ABAC

CODIR combine deux modèles d'autorisation :

**RBAC** (Role-Based) — l'utilisateur a un ou plusieurs `Role` au sein d'une `Organization` (Membre, DirecteurMétier, DG, Audit, Admin tenant…). Chaque rôle porte un set de `Permission` granulaires nommées par convention `app:resource:action` (ex. `decisions:decision:vote`, `budgets:scenario:create`).

**ABAC** (Attribute-Based) — par-dessus le RBAC, des policies évaluées au runtime filtrent ce que voit l'utilisateur. Exemple : `IsDecisionOwnerOrInSameDirection` permet à un DAF de voir toutes les décisions de la direction finance, mais à un manager de l'équipe Trésorerie de ne voir que celles touchant son périmètre.

L'implémentation tient en une classe `core.permissions.engine.PermissionEngine` interrogée par toutes les vues. Les policies sont déclaratives, testables, et exposées via une route `/api/v1/me/permissions` pour que le front cache l'arbre des droits et masque les boutons inaccessibles.

Détail complet dans [`13_rbac.md`](13_rbac.md).

## 7. Multi-tenant — implémentation

Choix : **isolation logique par discriminant `organization_id`** sur chaque table métier. Les éditions Sovereign passent en isolation physique par schéma PG dédié, sans changement applicatif (config Django par tenant).

Le `TenantMiddleware` extrait le tenant courant à partir : (a) du sous-domaine `acme.codir.app`, (b) du claim `org_id` du JWT, (c) d'un header `X-Tenant-ID` côté machine-to-machine. Il pose `request.organization` et le pousse dans un `threadlocal` accessible par les managers.

Le `core.managers.TenantManager` est utilisé par défaut sur tous les modèles métier. Toute requête `Decision.objects.all()` est traduite en `WHERE organization_id = current_tenant`. L'évasion volontaire (`Decision.unscoped.all()`) existe pour les jobs admin mais lève une métrique.

Détail dans [`09_architecture_multi_tenant.md`](09_architecture_multi_tenant.md).

## 8. Audit trail

Le module `audit_logs` expose un signal universel branché à `post_save`, `post_delete`, et à des actions explicites via service. Chaque entrée stocke : `actor`, `organization`, `action` (`created`/`updated`/`deleted`/`custom`), `target_type` (ContentType), `target_id`, `before` et `after` (JSON diff), `ip`, `user_agent`, `request_id`, `timestamp`, `signature` (HMAC SHA-256 de l'entrée pour garantir l'inaltérabilité).

L'export d'audit (CSV signé, PDF avec timestamps RFC 3161) est disponible pour les auditeurs externes.

## 9. Couche temps réel — vue backend

`config/asgi.py` monte deux protocoles : HTTP (Django classic) et WebSocket (Channels). Les consumers sont rangés dans `apps/<app>/consumers.py`. Le routing global :

```python
# config/routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.realtime.middleware import JWTAuthMiddleware
from apps.meetings.consumers import MeetingConsumer
from apps.dashboards.consumers import DashboardConsumer
from apps.notifications.consumers import NotificationConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path(r"ws/meetings/(?P<meeting_id>[\w-]+)/$", MeetingConsumer.as_asgi()),
    re_path(r"ws/dashboards/(?P<dashboard_id>[\w-]+)/$", DashboardConsumer.as_asgi()),
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
```

Détail dans [`12_websocket.md`](12_websocket.md).

## 10. Tasks Celery — organisation

Trois files distinctes : `default` (notifications légères, audit indexation), `ai` (transcription, génération PV, embeddings — workers spécialisés avec accès GPU), `reports` (génération PDF/Word/Excel — beaucoup d'I/O), `notifications` (envoi multi-canal), `integrations` (sync ERP / BI, pacing requis).

Celery Beat orchestre les tâches récurrentes : `recalculate_kpis_hourly`, `escalate_overdue_decisions`, `cleanup_expired_sessions`, `index_documents_to_opensearch`, `send_morning_digest_to_executives`.

## 11. Gestion des erreurs et observabilité

Toutes les exceptions HTTP passent par `core.exceptions.handlers.api_exception_handler` qui produit un JSON normalisé `{code, message, details, request_id, trace_id}`. Sentry intercepte automatiquement, en associant le `request_id` propagé via header.

Les logs sont structurés JSON, envoyés à Loki. Les métriques Prometheus sont exposées sur `/metrics` (custom : nombre de décisions créées par tenant, durée moyenne de génération PV, queue lag Celery, taux d'erreur par endpoint).

Détail dans [`21_monitoring.md`](21_monitoring.md).

## 12. Tests

Stack : `pytest` + `pytest-django` + `factory_boy` + `freezegun` + `responses`. Objectif : couverture ≥ 80 % lignes, 100 % sur les services critiques (auth, votes, génération PV).

Quatre niveaux : tests unitaires (services purs), tests d'intégration (API DRF avec base de test), tests de contrat (OpenAPI Schema vs. réponse), tests end-to-end avec Playwright sur le front + backend dockerisé.

## 13. Performance — cibles

| Indicateur | Cible |
|---|---|
| p50 endpoint REST | < 80 ms |
| p99 endpoint REST | < 400 ms |
| Démarrage cold worker Celery | < 5 s |
| Génération PV (1 h de réunion) | < 90 s |
| Recherche full-text (corpus 1 M docs) | < 250 ms |
| Connexion WebSocket (TLS handshake compris) | < 600 ms |
| Capacité (single node 4 vCPU 8 Go) | 200 req/s soutenu |

---

*Suite : [04 — Architecture frontend](04_architecture_frontend.md)*
