"""URLs meeting_recordings — branchées au routeur principal sous /api/v1/.

Routes :
- /api/v1/meetings/{meeting_id}/recordings/         (GET liste)
- /api/v1/meetings/{meeting_id}/recordings/start/   (POST)
- /api/v1/meetings/{meeting_id}/recordings/upload/  (POST multipart)
- /api/v1/recordings/                               (GET liste plat)
- /api/v1/recordings/{id}/                          (GET detail)
- /api/v1/recordings/{id}/process/                  (POST)
- /api/v1/recordings/{id}/status/                   (GET — polling)
- /api/v1/recordings/{id}/speakers/                 (GET)
- /api/v1/recordings/{id}/segments/                 (GET)
- /api/v1/recordings/{id}/speaker-mapping/          (POST)
- /api/v1/recordings/{id}/confirm-speakers/         (POST)
- /api/v1/recordings/{id}/generate-final-transcript/ (POST)
- /api/v1/recordings/{id}/generate-summary/         (POST)
- /api/v1/recordings/{id}/extract-decisions/        (POST)
- /api/v1/recordings/{id}/extract-actions/          (POST)
- /api/v1/recordings/{id}/extractions/              (GET)
- /api/v1/recordings/{id}/create-decisions/         (POST)
- /api/v1/recordings/{id}/create-action-plans/      (POST)
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MeetingRecordingNestedViewSet, MeetingRecordingViewSet

# Routeur flat /recordings/
router = DefaultRouter()
router.register(r"recordings", MeetingRecordingViewSet, basename="recordings")


# Routes nested — list + start + upload sous meetings/<uuid>/recordings/
nested_view = MeetingRecordingNestedViewSet.as_view({"get": "list"})
nested_start = MeetingRecordingNestedViewSet.as_view({"post": "start"})
nested_upload = MeetingRecordingNestedViewSet.as_view({"post": "upload"})


urlpatterns = [
    path("", include(router.urls)),
    path(
        "meetings/<uuid:meeting_id>/recordings/",
        nested_view,
        name="meeting-recordings-list",
    ),
    path(
        "meetings/<uuid:meeting_id>/recordings/start/",
        nested_start,
        name="meeting-recordings-start",
    ),
    path(
        "meetings/<uuid:meeting_id>/recordings/upload/",
        nested_upload,
        name="meeting-recordings-upload",
    ),
]
