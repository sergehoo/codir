"""URL routing principal — version bêta."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .health import healthz, ready

api_v1 = [
    # ── Auth & profil ──
    path("auth/", include("apps.accounts.urls")),
    # ── Tenant ──
    path("organizations/", include("apps.organizations.urls")),
    # ── Cœur métier bêta ──
    path("meetings/", include("apps.meetings.urls")),
    path("agendas/", include("apps.agendas.urls")),
    path("decisions/", include("apps.decisions.urls")),
    path("action-plans/", include("apps.action_plans.urls")),
    # ── Support ──
    path("documents/", include("apps.documents.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("audit-logs/", include("apps.audit_logs.urls")),
    path("dashboard/", include("apps.dashboards.urls")),
]

urlpatterns = [
    path("health/", healthz, name="healthz"),
    path("health/ready/", ready, name="ready"),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/v1/openapi.json", SpectacularAPIView.as_view(), name="schema"),
    path("docs/api/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
