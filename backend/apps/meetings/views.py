"""ViewSets DRF — meetings."""
import tempfile
from pathlib import Path

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import CanModifyMeeting, IsOrganizationMember

from . import services
from .filters import MeetingFilter
from .models import (
    Meeting, MeetingAttendance, MeetingMinutes,
    MeetingNote, MeetingParticipant, MeetingSeries,
)
from .serializers import (
    CancelMeetingSerializer, MeetingAttendanceSerializer,
    MeetingCreateSerializer, MeetingDetailSerializer,
    MeetingListSerializer, MeetingMinutesSerializer,
    MeetingNoteSerializer, MeetingParticipantSerializer,
    MeetingSeriesSerializer, RecordAttendanceSerializer,
)
from .imports.codir_importer import import_codir_data
from .imports.codir_pdf_extractor import extract_codir_pdf


class MeetingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember, CanModifyMeeting]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MeetingFilter
    search_fields = ["title", "description", "location"]
    ordering_fields = ["scheduled_start", "title", "status", "created_at"]
    ordering = ["-scheduled_start"]

    def get_queryset(self):
        return (
            Meeting.objects
            .select_related("chair", "secretary")
            .prefetch_related("participants", "attendances")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return MeetingListSerializer
        if self.action == "create":
            return MeetingCreateSerializer
        return MeetingDetailSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        m = services.create_meeting(
            organization=request.organization,
            created_by=request.user,
            data=ser.validated_data,
        )
        return Response(MeetingDetailSerializer(m).data, status=status.HTTP_201_CREATED)

    # ─── Transitions ────────────────────────────────────────────────
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        m = self.get_object()
        m = services.start_meeting(m, by_user=request.user)
        return Response(MeetingDetailSerializer(m).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        m = self.get_object()
        m = services.complete_meeting(m, by_user=request.user)
        return Response(MeetingDetailSerializer(m).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        m = self.get_object()
        ser = CancelMeetingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        m = services.cancel_meeting(m, by_user=request.user, reason=ser.validated_data.get("reason", ""))
        return Response(MeetingDetailSerializer(m).data)

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        """draft → scheduled (publication de l'invitation)."""
        m = self.get_object()
        if m.status != "draft":
            return Response({"detail": "Seul un brouillon peut être planifié."}, status=409)
        m.status = "scheduled"
        m.save(update_fields=["status", "updated_at"])
        return Response(MeetingDetailSerializer(m).data)

    # ─── Import d'un CR CODIR PDF ──────────────────────────────────
    # ─── Envoi manuel d'invitations email + ICS aux participants ──
    @action(detail=True, methods=["post"], url_path="send-invitations")
    def send_invitations(self, request, pk=None):
        """POST /api/v1/meetings/{id}/send-invitations/

        Envoie un email d'invitation à TOUS les participants du Meeting
        (avec fichier .ics joint pour ajout au calendrier Outlook/Google/Apple).
        Inclut le lien Teams/Zoom si ``video_url`` est défini.
        """
        from .invitations import send_invitations_for_meeting

        meeting = self.get_object()
        sent = send_invitations_for_meeting(meeting)
        return Response({
            "meeting_id": str(meeting.id),
            "invitations_sent": sent,
            "total_participants": meeting.participants.count(),
        })

    # ─── Génération du CR (relevé de conclusions) en .docx ─────────
    @action(detail=True, methods=["get"], url_path="export-cr-docx")
    def export_cr_docx(self, request, pk=None):
        """GET /api/v1/meetings/{id}/export-cr-docx/

        Génère un relevé de conclusions Word à partir des décisions et
        des tâches de la réunion, au format CODIR Kaydan.
        Retourne le fichier en attachment.
        """
        from django.http import HttpResponse
        from .imports.codir_doc_exporter import build_codir_minutes_docx

        meeting = self.get_object()
        bytes_io = build_codir_minutes_docx(meeting)
        filename = f"CR_CODIR_{meeting.scheduled_start:%Y%m%d}.docx"
        resp = HttpResponse(
            bytes_io.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @action(
        detail=False,
        methods=["post"],
        url_path="import-codir-pdf",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_codir_pdf(self, request):
        """Upload un PDF de relevé CODIR et crée Meeting + Participants +
        Decisions + ActionPlans + Tasks de façon idempotente.

        Body (multipart) :
            file : <fichier PDF>  (obligatoire)
            dry_run : "true" | "false"  (défaut "false")
        """
        upload = request.FILES.get("file")
        if not upload:
            raise ValidationError({"file": "Fichier PDF requis."})
        if not (upload.name or "").lower().endswith(".pdf"):
            raise ValidationError({"file": "Le fichier doit avoir l'extension .pdf"})

        dry_run = str(request.data.get("dry_run", "")).lower() in {"1", "true", "yes"}

        # Stocke le PDF en temp file (pdfplumber a besoin d'un path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for chunk in upload.chunks():
                tmp.write(chunk)
            tmp_path = Path(tmp.name)

        try:
            data = extract_codir_pdf(tmp_path)
            report = import_codir_data(
                data,
                organization=request.organization,
                actor=request.user,
                dry_run=dry_run,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        return Response({
            "extraction": {
                "reference": data["reference"],
                "date": str(data["date"]),
                "title": data["title"],
                "chair": data["chair"],
                "rapporteur": data["rapporteur"],
                "participants_total": len(data["participants"]),
                "actions_total": len(data["actions"]),
            },
            "report": report.to_dict(),
            "dry_run": dry_run,
        }, status=200 if not dry_run else 202)

    # ─── Sous-ressources ───────────────────────────────────────────
    @action(detail=True, methods=["get", "post"])
    def participants(self, request, pk=None):
        m = self.get_object()
        if request.method == "GET":
            qs = m.participants.select_related("user").all()
            return Response(MeetingParticipantSerializer(qs, many=True).data)
        ser = MeetingParticipantSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        p = services.add_participant(m, **ser.validated_data)
        return Response(MeetingParticipantSerializer(p).data, status=201)

    @action(detail=True, methods=["get", "post"])
    def attendance(self, request, pk=None):
        m = self.get_object()
        if request.method == "GET":
            qs = m.attendances.select_related("participant__user").all()
            return Response(MeetingAttendanceSerializer(qs, many=True).data)
        ser = RecordAttendanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        att = services.record_attendance(
            m, **ser.validated_data, recorded_by=request.user,
        )
        return Response(MeetingAttendanceSerializer(att).data, status=201)

    @action(detail=True, methods=["get"])
    def minutes(self, request, pk=None):
        m = self.get_object()
        minutes = MeetingMinutes.objects.filter(meeting=m).first()
        if minutes is None:
            return Response({"detail": "Compte rendu non disponible."}, status=404)
        return Response(MeetingMinutesSerializer(minutes).data)

    @action(detail=True, methods=["get", "post"])
    def notes(self, request, pk=None):
        m = self.get_object()
        if request.method == "GET":
            return Response(MeetingNoteSerializer(m.notes.all(), many=True).data)
        ser = MeetingNoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        n = MeetingNote.objects.create(
            organization=request.organization,
            meeting=m, author=request.user, **ser.validated_data,
        )
        return Response(MeetingNoteSerializer(n).data, status=201)

    # ─── Smart notes ──────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="smart-notes")
    def smart_notes(self, request, pk=None):
        """Renvoie la note courante + detected entities + mentions."""
        from .notes_serializers import (
            MeetingDetectedActionSerializer, MeetingDetectedDecisionSerializer,
            MeetingMentionSerializer, MeetingNoteFullSerializer,
        )

        empty = {"note": None, "detected_decisions": [], "orphan_actions": [], "mentions": []}
        try:
            from .models import MeetingDetectedAction, MeetingDetectedDecision, MeetingMention
            m = self.get_object()
            note = MeetingNote.objects.filter(meeting=m, is_current=True).first()
            decisions = MeetingDetectedDecision.objects.filter(meeting=m).prefetch_related("actions__assignee")
            orphans = MeetingDetectedAction.objects.filter(
                meeting=m, detected_decision__isnull=True,
            )
            mentions = MeetingMention.objects.filter(meeting=m).select_related("user")
            return Response({
                "note": MeetingNoteFullSerializer(note).data if note else None,
                "detected_decisions": MeetingDetectedDecisionSerializer(decisions, many=True).data,
                "orphan_actions": MeetingDetectedActionSerializer(orphans, many=True).data,
                "mentions": MeetingMentionSerializer(mentions, many=True).data,
            })
        except Exception:  # noqa: BLE001 — migration meetings.0002 manquante
            return Response(empty, status=200)

    @action(detail=True, methods=["post"], url_path="notes/autosave")
    def notes_autosave(self, request, pk=None):
        """POST /meetings/{id}/notes/autosave/  body: {content_json, content_md?}"""
        from .notes_services import autosave_notes, sync_detected_entities
        from .notes_serializers import MeetingNoteFullSerializer

        try:
            m = self.get_object()
            content_json = request.data.get("content_json") or {}
            content_md = request.data.get("content_md") or ""

            note = autosave_notes(
                meeting=m, author=request.user,
                content_json=content_json, content_md=content_md,
            )
            stats = {}
            if content_json:
                try:
                    stats = sync_detected_entities(meeting=m, note=note)
                except Exception as exc:  # noqa: BLE001
                    # Detected tables manquantes (migration pas faite) — on garde la note
                    stats = {"error": str(exc)[:200]}
            return Response({
                "note": MeetingNoteFullSerializer(note).data,
                "stats": stats,
            })
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.exception("notes_autosave failed")
            return Response(
                {"detail": "Migration meetings.0002 manquante ou erreur interne.",
                 "error": str(exc)[:400]},
                status=500,
            )

    @action(detail=True, methods=["post"], url_path="parse-notes")
    def parse_notes_action(self, request, pk=None):
        """Force un re-parse de la note courante et renvoie les détections."""
        from .notes_services import sync_detected_entities
        m = self.get_object()
        stats = sync_detected_entities(meeting=m)
        # Renvoie l'état complet à jour
        return self.smart_notes(request, pk=pk)

    @action(detail=True, methods=["post"], url_path="generate-decisions")
    def generate_decisions(self, request, pk=None):
        """Matérialise toutes les détections pending → vraies Decision/ActionPlan/ActionTask."""
        from .notes_services import publish_all_pending
        m = self.get_object()
        stats = publish_all_pending(meeting=m, by_user=request.user)
        return Response({"published": stats, "detail": "Publication effectuée."})

    @action(detail=True, methods=["post"], url_path="detected-decisions/(?P<dd_id>[^/.]+)/publish")
    def publish_one_decision(self, request, pk=None, dd_id=None):
        from .models import MeetingDetectedDecision
        from .notes_services import publish_detected_decision
        from .notes_serializers import MeetingDetectedDecisionSerializer
        m = self.get_object()
        dd = MeetingDetectedDecision.objects.filter(meeting=m, id=dd_id).first()
        if not dd:
            return Response({"detail": "Détection introuvable."}, status=404)
        publish_detected_decision(detected=dd, by_user=request.user)
        return Response(MeetingDetectedDecisionSerializer(dd).data)

    @action(detail=True, methods=["post"], url_path="detected-actions/(?P<da_id>[^/.]+)/publish")
    def publish_one_action(self, request, pk=None, da_id=None):
        from .models import MeetingDetectedAction
        from .notes_services import publish_detected_action
        from .notes_serializers import MeetingDetectedActionSerializer
        m = self.get_object()
        da = MeetingDetectedAction.objects.filter(meeting=m, id=da_id).first()
        if not da:
            return Response({"detail": "Détection introuvable."}, status=404)
        publish_detected_action(detected=da, by_user=request.user)
        return Response(MeetingDetectedActionSerializer(da).data)

    @action(detail=True, methods=["post"], url_path="detected-decisions/(?P<dd_id>[^/.]+)/dismiss")
    def dismiss_one_decision(self, request, pk=None, dd_id=None):
        from .models import DetectedDecisionStatus, MeetingDetectedDecision
        m = self.get_object()
        dd = MeetingDetectedDecision.objects.filter(meeting=m, id=dd_id).first()
        if not dd:
            return Response({"detail": "Détection introuvable."}, status=404)
        dd.status = DetectedDecisionStatus.DISMISSED
        dd.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Rejetée."})

    @action(detail=True, methods=["get"], url_path="mention-candidates")
    def mention_candidates(self, request, pk=None):
        """Liste des users candidats pour l'autocomplete @ — priorise participants."""
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        from apps.accounts.serializers import UserMiniSerializer
        User = get_user_model()
        try:
            m = self.get_object()
            q = request.query_params.get("q", "").strip()

            # 1) Participants — via MeetingParticipant (plus robuste qu'une reverse FK)
            participant_ids = list(m.participants.exclude(user__isnull=True).values_list("user_id", flat=True))

            # 2) Tous les membres actifs de l'org (via Memberships)
            org_users_qs = User.objects.filter(
                memberships__organization=request.organization,
                is_active=True,
            ).distinct()

            if q:
                org_users_qs = org_users_qs.filter(
                    Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q),
                )

            org_users = list(org_users_qs[:25])

            # Tri : participants d'abord, puis ordre alpha
            def _key(u):
                return (0 if u.id in participant_ids else 1,
                        (u.first_name or u.email).lower())
            merged = sorted(org_users, key=_key)[:15]
            return Response(UserMiniSerializer(merged, many=True).data)
        except Exception as exc:  # noqa: BLE001
            # Graceful fallback (migration pas appliquée par ex.)
            return Response([], status=200)


class MeetingParticipantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = MeetingParticipantSerializer

    def get_queryset(self):
        return MeetingParticipant.objects.select_related("user", "meeting").all()


class MeetingSeriesViewSet(viewsets.ModelViewSet):
    """CRUD des séries récurrentes (templates de réunions).

    Endpoint custom ``POST /series/{id}/generate-now/`` → déclenche immédiatement
    la génération des instances sans attendre le cron quotidien.
    """
    permission_classes = [IsOrganizationMember]
    serializer_class = MeetingSeriesSerializer

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        qs = (
            MeetingSeries.unscoped
            .select_related("default_chair", "default_secretary", "organization")
            .prefetch_related("default_participants")
            .all()
        )
        if org is not None:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org = getattr(self.request, "organization", None)
        serializer.save(organization=org)

    @action(detail=True, methods=["post"], url_path="generate-now")
    def generate_now(self, request, pk=None):
        """Génère immédiatement les instances pour CETTE série (sans attendre le cron)."""
        from .tasks import generate_recurring_meetings, _occurrence_dates
        from datetime import datetime, timedelta
        from django.utils import timezone as dj_tz
        from apps.common.enums import MeetingStatus, ParticipantRole

        series = self.get_object()
        today = dj_tz.localdate()
        target_end = today + timedelta(weeks=series.generate_weeks_ahead)
        if series.ends_on and series.ends_on < target_end:
            target_end = series.ends_on
        start_from = series.last_generated_until or series.starts_on or today
        if start_from < today:
            start_from = today

        occurrences = _occurrence_dates(series, start_from, target_end)
        local_tz = dj_tz.get_current_timezone()
        created = 0

        for occ_date in occurrences:
            start_dt = dj_tz.make_aware(
                datetime.combine(occ_date, series.time), local_tz,
            )
            end_dt = start_dt + timedelta(minutes=series.duration_minutes)
            meeting, was_created = Meeting.unscoped.get_or_create(
                series=series,
                scheduled_start=start_dt,
                defaults={
                    "organization": series.organization,
                    "title": f"{series.title} — {occ_date:%d/%m/%Y}",
                    "description": series.description,
                    "meeting_type": series.meeting_type,
                    "scheduled_end": end_dt,
                    "status": MeetingStatus.SCHEDULED,
                    "location": series.location,
                    "video_url": series.video_url,
                    "chair": series.default_chair,
                    "secretary": series.default_secretary,
                },
            )
            if was_created:
                created += 1
                for user in series.default_participants.all():
                    role = ParticipantRole.MEMBER
                    if series.default_chair_id == user.id:
                        role = ParticipantRole.CHAIR
                    elif series.default_secretary_id == user.id:
                        role = ParticipantRole.SECRETARY
                    MeetingParticipant.unscoped.get_or_create(
                        organization=series.organization,
                        meeting=meeting, user=user,
                        defaults={"role": role, "is_required": True, "external_email": None},
                    )

        series.last_generated_until = target_end
        series.save(update_fields=["last_generated_until"])
        return Response({
            "series_id": str(series.id),
            "instances_created": created,
            "generated_until": str(target_end),
        })
