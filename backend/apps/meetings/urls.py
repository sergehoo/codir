from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    MeetingParticipantViewSet, MeetingSeriesViewSet, MeetingViewSet,
)

# ⚠ Routes explicites en premier pour éviter le conflit `<pk>/` qui capterait
# `series/`, `participants/`, etc. (cf. bug action-plans/tasks/all/)
series_router = DefaultRouter()
series_router.register(r"", MeetingSeriesViewSet, basename="meeting-series")

participants_router = DefaultRouter()
participants_router.register(r"", MeetingParticipantViewSet, basename="meeting-participant")

main_router = DefaultRouter()
main_router.register(r"", MeetingViewSet, basename="meeting")

urlpatterns = [
    path("series/", include(series_router.urls)),
    path("participants/", include(participants_router.urls)),
    path("", include(main_router.urls)),
]
