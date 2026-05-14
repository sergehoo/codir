from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationPreferenceViewSet, NotificationViewSet,
    dashboard_summary, test_email,
)

router = DefaultRouter()
router.register(r"preferences", NotificationPreferenceViewSet, basename="notif-preference")
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [
    path("test-email/", test_email, name="notif-test-email"),
    path("dashboard/summary/", dashboard_summary, name="notif-dashboard-summary"),
] + router.urls
