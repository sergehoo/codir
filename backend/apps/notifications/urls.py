from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationPreferenceViewSet, NotificationViewSet,
    dashboard_summary, push_subscribe, push_unsubscribe, push_vapid_public_key,
    test_email,
)

router = DefaultRouter()
router.register(r"preferences", NotificationPreferenceViewSet, basename="notif-preference")
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [
    path("test-email/", test_email, name="notif-test-email"),
    path("dashboard/summary/", dashboard_summary, name="notif-dashboard-summary"),
    # ── Push Web (Lot 6) ──
    path("push/vapid-public-key/", push_vapid_public_key, name="push-vapid-key"),
    path("push/subscribe/",         push_subscribe,        name="push-subscribe"),
    path("push/unsubscribe/",       push_unsubscribe,      name="push-unsubscribe"),
] + router.urls
