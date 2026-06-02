"""Views DRF — endpoints meeting_recordings.

Deux groupes :
1. Nested sous /meetings/{meeting_id}/recordings/
   - list, retrieve, start, upload.
2. Flat sous /recordings/{recording_id}/...
   - status, speakers, segments, mappings, validation IA, push decisions/actions.

Toutes les vues sont tenant-aware via DRF + filtres explicites + permission.
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AIExtractionStatus, AIExtractionType,
    DetectedSpeaker, MeetingRecording, RecordingAIExtraction,
    RecordingStatus, SpeakerSegment,
)
from .permissions import CanAccessMeetingRecording, CanRecordOnMeeting
from .serializers import (
    BulkSpeakerMappingInputSerializer,
    DetectedSpeakerSerializer,
    MeetingRecordingDetailSerializer,
    MeetingRecordingListSerializer,
    RecordingAIExtractionSerializer,
    SpeakerSegmentSerializer,
    StartRecordingSerializer,
    UploadRecordingSerializer,
    ValidateExtractionSerializer,
)
from .services import (
    confirm_all_mappings, create_recording, generate_final_transcript,
    mark_uploaded, map_speaker_to_participant,
    push_action_plan_to_module, push_decision_to_module,
    update_status,
)
from .tasks import (
    generate_final_transcript_task, process_recording_task,
    summarize_recording_task,
)

logger = logging.getLogger(__name__)


def _get_meeting_or_404(meeting_id):
    from apps.meetings.models import Meeting
    return get_object_or_404(Meeting.objects, id=meeting_id)


# ─── Nested : /meetings/{meeting_id}/recordings/ ────────────────

class MeetingRecordingNestedViewSet(viewsets.ViewSet):
    """List + create (start) + upload sous une réunion donnée."""

    permission_classes = [IsAuthenticated, CanRecordOnMeeting]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def list(self, request, meeting_id=None):
        meeting = _get_meeting_or_404(meeting_id)
        qs = (
            MeetingRecording.objects
            .filter(meeting=meeting)
            .order_by("-created_at")
        )
        return Response(
            MeetingRecordingListSerializer(qs, many=True).data,
        )

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request, meeting_id=None):
        """POST /meetings/{id}/recordings/start/ — créé l'objet AVANT upload."""
        meeting = _get_meeting_or_404(meeting_id)
        ser = StartRecordingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rec = create_recording(
            meeting=meeting,
            recorded_by=request.user,
            title=ser.validated_data.get("title", ""),
            consent_acknowledged=ser.validated_data.get("consent_acknowledged", False),
        )
        update_status(rec, RecordingStatus.RECORDING)
        return Response(
            MeetingRecordingDetailSerializer(rec).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="upload",
            parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, meeting_id=None):
        """POST /meetings/{id}/recordings/upload/ — attache l'audio + déclenche pipeline."""
        meeting = _get_meeting_or_404(meeting_id)
        ser = UploadRecordingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        rec_id = ser.validated_data.get("recording_id")
        if rec_id:
            rec = get_object_or_404(MeetingRecording.objects, id=rec_id, meeting=meeting)
        else:
            rec = create_recording(
                meeting=meeting,
                recorded_by=request.user,
                title=ser.validated_data.get("title", ""),
                consent_acknowledged=ser.validated_data.get("consent_acknowledged", False),
            )

        audio = ser.validated_data["audio"]
        update_status(rec, RecordingStatus.UPLOADING)
        mark_uploaded(
            rec,
            file_obj=audio,
            mime_type=audio.content_type or "",
            original_filename=getattr(audio, "name", ""),
            duration_seconds=ser.validated_data.get("duration_seconds"),
        )

        # Déclenche le pipeline async (transcription + diarisation).
        process_recording_task.delay(str(rec.id))

        return Response(
            MeetingRecordingDetailSerializer(rec).data,
            status=status.HTTP_202_ACCEPTED,
        )


# ─── Flat : /recordings/{id}/... ─────────────────────────────────

class MeetingRecordingViewSet(viewsets.ReadOnlyModelViewSet):
    """retrieve + update partiel + actions custom sur 1 recording."""

    permission_classes = [IsAuthenticated, CanAccessMeetingRecording]
    queryset = MeetingRecording.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return MeetingRecordingListSerializer
        return MeetingRecordingDetailSerializer

    def list(self, request, *args, **kwargs):
        # /recordings/?meeting=<id> — utile pour les widgets dashboard.
        qs = self.get_queryset().order_by("-created_at")
        meeting_id = request.query_params.get("meeting")
        if meeting_id:
            qs = qs.filter(meeting_id=meeting_id)
        return Response(
            MeetingRecordingListSerializer(qs[:50], many=True).data,
        )

    # ─── Pipeline ────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        rec = self.get_object()
        process_recording_task.delay(str(rec.id))
        return Response({"status": "queued", "recording_id": str(rec.id)})

    @action(detail=True, methods=["get"], url_path="status")
    def status_(self, request, pk=None):
        """GET /recordings/{id}/status/ — polling léger pour le front."""
        rec = self.get_object()
        return Response({
            "id": str(rec.id),
            "status": rec.status,
            "duration_seconds": rec.duration_seconds,
            "speakers_count": rec.speakers.count(),
            "segments_count": rec.segments.count(),
            "has_summary": bool(rec.summary),
            "has_decisions_drafts": rec.extractions.filter(
                extraction_type=AIExtractionType.DECISION,
                status=AIExtractionStatus.DRAFT,
            ).exists(),
            "has_actions_drafts": rec.extractions.filter(
                extraction_type=AIExtractionType.ACTION,
                status=AIExtractionStatus.DRAFT,
            ).exists(),
            "error_message": rec.error_message,
        })

    # ─── Speakers ────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="speakers")
    def speakers(self, request, pk=None):
        rec = self.get_object()
        speakers = rec.speakers.all().order_by("speaker_label")
        return Response(DetectedSpeakerSerializer(speakers, many=True).data)

    @action(detail=True, methods=["get"], url_path="segments")
    def segments(self, request, pk=None):
        rec = self.get_object()
        segs = rec.segments.all().order_by("start_time")
        return Response(SpeakerSegmentSerializer(segs, many=True).data)

    @action(detail=True, methods=["post"], url_path="speaker-mapping")
    def speaker_mapping(self, request, pk=None):
        """POST /recordings/{id}/speaker-mapping/ — payload : 1 ou N mappings.

        Format bulk (recommandé) :
            { "mappings": [ {"speaker_label": "SPEAKER_00", "participant_id": "..."}, ... ] }
        """
        rec = self.get_object()
        ser = BulkSpeakerMappingInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            from apps.accounts.models import User
        except Exception:  # noqa: BLE001
            return Response({"detail": "accounts indisponible"}, status=500)

        results = []
        for m in ser.validated_data["mappings"]:
            participant = User.objects.filter(id=m["participant_id"]).first()
            if participant is None:
                return Response(
                    {"detail": f"Participant inconnu : {m['participant_id']}"},
                    status=400,
                )
            sp = map_speaker_to_participant(
                recording=rec,
                speaker_label=m["speaker_label"],
                participant=participant,
                confirmed_by=request.user,
                notes=m.get("notes", ""),
            )
            results.append(DetectedSpeakerSerializer(sp).data)
        return Response({"updated": results})

    @action(detail=True, methods=["post"], url_path="confirm-speakers")
    def confirm_speakers(self, request, pk=None):
        """Marque tous les speakers comme confirmés, puis génère le transcript final + résumé."""
        rec = self.get_object()
        try:
            confirm_all_mappings(recording=rec, confirmed_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        # Chaîne async : final transcript → summary → extractions.
        generate_final_transcript_task.delay(str(rec.id))
        summarize_recording_task.apply_async(
            args=[str(rec.id)], countdown=2,
        )
        update_status(rec, RecordingStatus.GENERATING_FINAL_TRANSCRIPT)
        return Response({"status": "queued"})

    # ─── Final transcript ────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="generate-final-transcript")
    def generate_final_transcript_(self, request, pk=None):
        rec = self.get_object()
        out = generate_final_transcript(rec)
        return Response({"segments": len(out), "transcript_final": out})

    # ─── Résumé IA ───────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="generate-summary")
    def generate_summary_(self, request, pk=None):
        rec = self.get_object()
        summarize_recording_task.delay(str(rec.id))
        return Response({"status": "queued"})

    @action(detail=True, methods=["post"], url_path="extract-decisions")
    def extract_decisions_(self, request, pk=None):
        from .tasks import extract_decisions_task
        rec = self.get_object()
        extract_decisions_task.delay(str(rec.id))
        return Response({"status": "queued"})

    @action(detail=True, methods=["post"], url_path="extract-actions")
    def extract_actions_(self, request, pk=None):
        from .tasks import extract_action_items_task
        rec = self.get_object()
        extract_action_items_task.delay(str(rec.id))
        return Response({"status": "queued"})

    # ─── Validation IA → push modules cibles ─────────────────────

    @action(detail=True, methods=["get"], url_path="extractions")
    def extractions(self, request, pk=None):
        """GET /recordings/{id}/extractions/ — liste des brouillons IA."""
        rec = self.get_object()
        qs = rec.extractions.all().order_by("extraction_type", "-created_at")
        # Filtre optionnel ?type=decision
        t = request.query_params.get("type")
        if t:
            qs = qs.filter(extraction_type=t)
        return Response(RecordingAIExtractionSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="create-decisions")
    def create_decisions(self, request, pk=None):
        """Valide N brouillons décision et crée les Decisions correspondantes."""
        rec = self.get_object()
        ser = ValidateExtractionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created = []
        for eid in ser.validated_data["extraction_ids"]:
            ext = RecordingAIExtraction.objects.filter(
                id=eid, recording=rec,
                extraction_type=AIExtractionType.DECISION,
            ).first()
            if ext is None:
                continue
            try:
                d = push_decision_to_module(extraction=ext, validated_by=request.user)
                created.append({"extraction_id": str(ext.id), "decision_id": str(d.id)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("push decision KO")
                created.append({"extraction_id": str(ext.id), "error": str(exc)})
        return Response({"created": created})

    @action(detail=True, methods=["post"], url_path="create-action-plans")
    def create_action_plans(self, request, pk=None):
        """Valide N brouillons action et crée les ActionPlan/ActionTask correspondants."""
        rec = self.get_object()
        ser = ValidateExtractionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created = []
        for eid in ser.validated_data["extraction_ids"]:
            ext = RecordingAIExtraction.objects.filter(
                id=eid, recording=rec,
                extraction_type=AIExtractionType.ACTION,
            ).first()
            if ext is None:
                continue
            try:
                plan = push_action_plan_to_module(extraction=ext, validated_by=request.user)
                created.append({"extraction_id": str(ext.id), "action_plan_id": str(plan.id)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("push action_plan KO")
                created.append({"extraction_id": str(ext.id), "error": str(exc)})
        return Response({"created": created})
