"""URLs meeting_recordings — branchées au routeur principal sous /api/v1/.

Routes :
- /api/v1/meetings/{meeting_id}/recordings/         (GET liste)
- /api/v1/meetings/{meeting_id}/recordings/start/   (POST)
- /api/v1/meetings/{meeting_id}/recordings/upload/  (POST multipart single-shot)
- /api/v1/meetings/{meeting_id}/recordings/upload/init/   (POST chunked init)
- /api/v1/recordings/upload/{recording_id}/chunks/{idx}/  (PUT chunk binaire)
- /api/v1/recordings/upload/{recording_id}/status/        (GET chunked status)
- /api/v1/recordings/upload/{recording_id}/complete/      (POST chunked complete)
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

from .views import (
    MeetingRecordingNestedViewSet, MeetingRecordingViewSet,
    chunked_upload_chunk_view, chunked_upload_complete_view,
    chunked_upload_init_view, chunked_upload_status_view,
)

# Routeur flat /recordings/
router = DefaultRouter()
router.register(r"recordings", MeetingRecordingViewSet, basename="recordings")


# Routes nested — list + start + upload sous meetings/<uuid>/recordings/
nested_view = MeetingRecordingNestedViewSet.as_view({"get": "list"})
nested_start = MeetingRecordingNestedViewSet.as_view({"post": "start"})
nested_upload = MeetingRecordingNestedViewSet.as_view({"post": "upload"})


urlpatterns = [
    # ⚠ Les routes chunked DOIVENT être déclarées AVANT `include(router.urls)`
    # car DefaultRouter génère /recordings/<pk>/... qui matcherait
    # /recordings/upload/<uuid>/ avec pk=upload, capturant nos routes.
    path(
        "recordings/upload/<uuid:recording_id>/chunks/<int:chunk_index>/",
        chunked_upload_chunk_view,
        name="recordings-chunked-chunk",
    ),
    path(
        "recordings/upload/<uuid:recording_id>/status/",
        chunked_upload_status_view,
        name="recordings-chunked-status",
    ),
    path(
        "recordings/upload/<uuid:recording_id>/complete/",
        chunked_upload_complete_view,
        name="recordings-chunked-complete",
    ),
    path(
        "meetings/<uuid:meeting_id>/recordings/upload/init/",
        chunked_upload_init_view,
        name="meeting-recordings-upload-init",
    ),
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
