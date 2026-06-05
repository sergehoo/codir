from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AccessLogListView, AuditLogViewSet

router = DefaultRouter()
router.register(r"", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    # Doit être déclaré AVANT l'inclusion du router pour ne pas être capturé
    # par le routeur racine (qui matche /<uuid>/).
    path("access/", AccessLogListView.as_view(), name="access-logs"),
] + router.urls
