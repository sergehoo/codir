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
    RecordingChunk, RecordingStatus, SpeakerSegment,
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


def _stream_file_response(file_field, *, content_type: str, filename: str):
    """Stream un FileField (MinIO/S3/FS) au navigateur via Django.

    Avantages vs. URL présignée :
    - Django gère les permissions (sécurité)
    - Pas besoin que le storage soit accessible publiquement
    - Pas de problème de signature/expiration
    - Support du range-request (lecture partielle audio) à terme

    Pour les gros fichiers (>200 Mo), Django stream par chunks ; le navigateur
    peut lancer la lecture audio dès les premiers Ko reçus.
    """
    from django.http import StreamingHttpResponse, Http404

    bucket = getattr(file_field.storage, "bucket_name", "?")
    name = file_field.name or "?"
    logger.info(
        "_stream_file_response: name=%s bucket=%s storage=%s",
        name, bucket, type(file_field.storage).__name__,
    )
    try:
        file_field.open("rb")
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Impossible d'ouvrir le fichier %s (bucket=%s, storage=%s): %s",
            name, bucket, type(file_field.storage).__name__, exc,
        )
        raise Http404(f"Fichier inaccessible (storage={bucket}).")

    def _iter_chunks():
        try:
            while True:
                chunk = file_field.read(64 * 1024)  # 64 Ko
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                file_field.close()
            except Exception:  # noqa: BLE001
                pass

    response = StreamingHttpResponse(
        _iter_chunks(),
        content_type=content_type,
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    # Cache léger côté navigateur (file content immutable une fois généré)
    response["Cache-Control"] = "private, max-age=3600"
    # Header utile pour le lecteur audio HTML5 (autorise le seek si supporté)
    response["Accept-Ranges"] = "bytes"
    return response


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
            MeetingRecordingListSerializer(
                qs, many=True, context={"request": request},
            ).data,
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
            MeetingRecordingDetailSerializer(rec, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="upload",
            parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, meeting_id=None):
        """POST /meetings/{id}/recordings/upload/ — attache l'audio + déclenche pipeline.

        Stratégie d'erreur :
        - Chaque étape (validation, création, save fichier, queue Celery) est
          isolée pour pouvoir renvoyer un message précis au front (pas un 500
          opaque).
        - Si le save vers le storage par défaut (S3) plante (clés manquantes,
          bucket inexistant, network), on log l'erreur et on remonte 502 avec
          un message exploitable plutôt qu'un 500.
        """
        meeting = _get_meeting_or_404(meeting_id)

        # ── 1. Validation payload ──────────────────────────────
        ser = UploadRecordingSerializer(data=request.data)
        try:
            ser.is_valid(raise_exception=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("upload: validation KO meeting=%s err=%s", meeting_id, exc)
            raise

        audio = ser.validated_data["audio"]
        logger.info(
            "upload: meeting=%s file=%s size=%s mime=%s user=%s",
            meeting_id, getattr(audio, "name", "?"), getattr(audio, "size", "?"),
            audio.content_type, request.user,
        )

        # ── 2. Récupération ou création du recording ───────────
        rec_id = ser.validated_data.get("recording_id")
        try:
            if rec_id:
                rec = get_object_or_404(
                    MeetingRecording.objects, id=rec_id, meeting=meeting,
                )
            else:
                rec = create_recording(
                    meeting=meeting,
                    recorded_by=request.user,
                    title=ser.validated_data.get("title", ""),
                    consent_acknowledged=ser.validated_data.get(
                        "consent_acknowledged", False,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("upload: create_recording KO")
            return Response(
                {"detail": f"Impossible de créer l'enregistrement : {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── 3. Save du FileField (le point critique) ───────────
        update_status(rec, RecordingStatus.UPLOADING)
        try:
            mark_uploaded(
                rec,
                file_obj=audio,
                mime_type=audio.content_type or "",
                original_filename=getattr(audio, "name", ""),
                duration_seconds=ser.validated_data.get("duration_seconds"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "upload: mark_uploaded KO recording=%s storage=%s",
                rec.id,
                type(rec.audio_file.storage).__name__,
            )
            # On marque le recording en FAILED pour ne pas le laisser fantôme.
            try:
                from .services import mark_failed
                mark_failed(rec, f"Erreur stockage : {exc}")
            except Exception:  # noqa: BLE001
                pass
            # 502 Bad Gateway : signale clairement que c'est une dépendance
            # externe (S3) qui est en cause, pas un bug logique.
            return Response(
                {
                    "detail": "Échec de l'enregistrement du fichier audio sur le stockage. "
                              f"Cause : {type(exc).__name__}: {exc}. "
                              "Vérifiez les variables d'environnement S3 (S3_ENDPOINT, "
                              "S3_ACCESS_KEY, S3_SECRET_KEY, RECORDING_S3_BUCKET) ou "
                              "basculez sur un stockage local en dev.",
                    "recording_id": str(rec.id),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ── 4. Déclenchement du pipeline Celery ────────────────
        try:
            process_recording_task.delay(str(rec.id))
        except Exception as exc:  # noqa: BLE001
            logger.exception("upload: enqueue Celery KO recording=%s", rec.id)
            # On ne marque pas failed : l'audio est uploadé, l'utilisateur
            # pourra relancer manuellement /recordings/{id}/process/.
            return Response(
                {
                    "detail": "Audio uploadé mais impossible de démarrer la transcription "
                              f"({exc}). Le worker Celery est-il démarré ?",
                    "recording_id": str(rec.id),
                    "recording": MeetingRecordingDetailSerializer(
                        rec, context={"request": request},
                    ).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(
            MeetingRecordingDetailSerializer(rec, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )


# ─── Flat : /recordings/{id}/... ─────────────────────────────────

class MeetingRecordingViewSet(viewsets.ReadOnlyModelViewSet):
    """retrieve + update partiel + actions custom sur 1 recording.

    ⚠️ IMPORTANT : on définit `get_queryset()` au lieu de `queryset = ...`.

    Le pattern `queryset = Model.objects.all()` s'évalue au moment de l'import
    du module — alors que `current_organization` est encore None côté ContextVar
    de TenantManager. Résultat : le queryset retourne `.none()` et toutes les
    requêtes (incluant le polling `/status/`) renvoient 404 même si le
    recording existe.

    `get_queryset(self)` est appelé à chaque requête, après que la middleware
    tenant a activé l'organisation courante → comportement attendu.
    """

    permission_classes = [IsAuthenticated, CanAccessMeetingRecording]

    def get_queryset(self):
        # Évalué à chaque requête (avec tenant context actif).
        return (
            MeetingRecording.objects
            .select_related("meeting", "recorded_by", "organization")
            .prefetch_related("speakers", "segments", "extractions")
        )

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
            MeetingRecordingListSerializer(
                qs[:50], many=True, context={"request": request},
            ).data,
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
        # Le serializer aura besoin de la request pour construire l'URL absolue
        # du proxy audio (au lieu de l'URL S3/MinIO public).
        ser = DetectedSpeakerSerializer(
            speakers, many=True, context={"request": request},
        )
        return Response(ser.data)

    @action(detail=True, methods=["get"], url_path="segments")
    def segments(self, request, pk=None):
        rec = self.get_object()
        segs = rec.segments.all().order_by("start_time")
        return Response(SpeakerSegmentSerializer(segs, many=True).data)

    # ─── Streaming audio (proxy depuis MinIO interne) ──────────
    # Permet au navigateur d'écouter l'audio sans dépendre que MinIO soit
    # accessible publiquement (DNS/cert/firewall). Django lit le fichier
    # depuis le storage interne et le streame au client avec auth + permissions.

    # ─── Streaming audio ──────────────────────────────────────
    # Note auth : les balises HTML <audio>/<video> n'envoient PAS de header
    # Authorization → on accepte ALTERNATIVEMENT un token signé en query
    # string (?token=...). Voir `audio_tokens.verify_audio_token`.

    def get_permissions(self):
        # Override : pour les routes de stream audio, on contourne le check
        # JWT habituel (qui retournerait 401) et on délègue à la vérification
        # token explicite dans la méthode.
        if self.action in ("stream_audio", "stream_speaker_sample"):
            from rest_framework.permissions import AllowAny
            return [AllowAny()]
        return super().get_permissions()

    def _verify_audio_access(self, request, recording):
        """Vérifie l'accès au stream via JWT OU token signé.

        Retourne True si OK, sinon retourne une Response 401/403.
        """
        from rest_framework.response import Response
        from .audio_tokens import verify_audio_token

        # Cas A : token signé en query (utilisé par les balises HTML <audio>)
        token = request.GET.get("token") or request.query_params.get("token")
        if token:
            # Le path qu'on a signé est le path complet de la requête actuelle
            # (sans query string). On reconstruit pour valider.
            payload = verify_audio_token(token=token, resource_path=request.path)
            if payload is None:
                return Response(
                    {"detail": "Token audio invalide ou expiré."},
                    status=401,
                )
            return True

        # Cas B : Bearer JWT classique (utilisé par fetch() côté API)
        # On lance manuellement l'authentification + permission DRF.
        from rest_framework_simplejwt.authentication import JWTAuthentication
        try:
            auth = JWTAuthentication().authenticate(request)
        except Exception:  # noqa: BLE001
            auth = None
        if auth is None:
            return Response(
                {"detail": "Authentification requise (Bearer ou token)."},
                status=401,
            )
        request.user, _ = auth
        # Re-check permission sur l'objet recording
        if not CanAccessMeetingRecording().has_object_permission(
            request, self, recording,
        ):
            return Response({"detail": "Accès refusé."}, status=403)
        return True

    @action(detail=True, methods=["get"], url_path="audio")
    def stream_audio(self, request, pk=None):
        """GET /recordings/{id}/audio/?token=... — stream audio complet."""
        from django.http import Http404
        # /!\ get_object() utilise get_queryset() qui scope au tenant courant.
        # Comme on bypass l'auth ici, on lookup en unscoped puis on valide le token.
        rec = MeetingRecording.unscoped.filter(id=pk).first()
        if rec is None:
            raise Http404("Recording introuvable.")
        check = self._verify_audio_access(request, rec)
        if check is not True:
            return check
        if not rec.audio_file:
            raise Http404("Pas d'audio attaché.")
        return _stream_file_response(
            rec.audio_file,
            content_type=rec.mime_type or "audio/webm",
            filename=f"recording-{rec.id}.webm",
        )

    @action(detail=True, methods=["get"],
            url_path=r"speakers/(?P<speaker_label>[A-Za-z0-9_-]+)/sample")
    def stream_speaker_sample(self, request, pk=None, speaker_label=None):
        """GET /recordings/{id}/speakers/{label}/sample/?token=... — extrait audio.

        ⚠️ AUTH PAR TOKEN : on bypass JWT/permission DRF (AllowAny dans
        get_permissions). Conséquence : la TenantMiddleware n'a pas activé
        de tenant context → on DOIT utiliser .unscoped sur TOUS les lookups,
        sinon le manager TenantManager retourne .none() → 404 systématique.
        """
        from django.http import Http404
        from .models import DetectedSpeaker

        rec = MeetingRecording.unscoped.filter(id=pk).first()
        if rec is None:
            logger.warning("stream_speaker_sample: recording %s introuvable", pk)
            raise Http404("Recording introuvable.")
        check = self._verify_audio_access(request, rec)
        if check is not True:
            return check

        # IMPORTANT : .unscoped car pas de tenant context quand auth=token
        speaker = DetectedSpeaker.unscoped.filter(
            recording=rec, speaker_label=speaker_label,
        ).first()
        if speaker is None:
            logger.warning(
                "stream_speaker_sample: speaker %s introuvable sur recording %s "
                "(check .unscoped DB)", speaker_label, pk,
            )
            raise Http404("Speaker inconnu.")
        if not speaker.sample_audio or not speaker.sample_audio.name:
            logger.warning(
                "stream_speaker_sample: sample_audio vide pour %s/%s",
                pk, speaker_label,
            )
            raise Http404("Extrait audio non généré (pydub probablement KO lors de la diarisation).")
        logger.info(
            "stream_speaker_sample: %s/%s → %s",
            pk, speaker_label, speaker.sample_audio.name,
        )
        return _stream_file_response(
            speaker.sample_audio,
            content_type="audio/mpeg",
            filename=f"{speaker_label}.mp3",
        )

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

    # ─── Édition du CR (summary + ai_minutes) ────────────────
    # L'utilisateur peut ajuster le résumé IA avant export. PATCH partiel,
    # uniquement chair/secretary/recorded_by autorisés (cf. permission).

    @action(detail=True, methods=["patch"], url_path="minutes")
    def update_minutes(self, request, pk=None):
        """PATCH /recordings/{id}/minutes/ — édite summary et/ou ai_minutes.

        Body : { "summary": "...", "ai_minutes": "..." } (les 2 optionnels)
        """
        from django.utils import timezone
        rec = self.get_object()
        # Vérifie écriture (CanAccessMeetingRecording.has_object_permission)
        # — la classe permission est déjà appliquée via get_permissions.

        update_fields = []
        if "summary" in request.data:
            new_summary = (request.data.get("summary") or "")[:50000]
            rec.summary = new_summary
            update_fields.append("summary")
        if "ai_minutes" in request.data:
            new_minutes = (request.data.get("ai_minutes") or "")[:200000]
            rec.ai_minutes = new_minutes
            update_fields.append("ai_minutes")

        if not update_fields:
            return Response(
                {"detail": "Aucun champ à mettre à jour (summary ou ai_minutes)."},
                status=400,
            )

        update_fields.append("updated_at")
        rec.save(update_fields=update_fields)

        # Audit log
        try:
            from apps.audit_logs.services import log as audit_log
            audit_log(
                action="updated", target=rec,
                description=f"Compte rendu IA modifié manuellement par {request.user}",
            )
        except Exception:  # noqa: BLE001
            pass

        return Response(MeetingRecordingDetailSerializer(
            rec, context={"request": request},
        ).data)

    # ─── Exports DOCX / PDF ──────────────────────────────────

    @action(detail=True, methods=["get"], url_path="export/docx")
    def export_docx(self, request, pk=None):
        """GET /recordings/{id}/export/docx/ — télécharge le CR au format Word."""
        from django.http import HttpResponse
        from .services.export import generate_minutes_docx

        rec = self.get_object()
        try:
            data = generate_minutes_docx(rec)
        except Exception as exc:  # noqa: BLE001
            logger.exception("export_docx KO")
            return Response(
                {"detail": f"Erreur génération DOCX : {exc}"},
                status=500,
            )

        filename = _slug_filename(rec, "docx")
        response = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["get"], url_path="export/pdf")
    def export_pdf(self, request, pk=None):
        """GET /recordings/{id}/export/pdf/ — télécharge le CR au format PDF."""
        from django.http import HttpResponse
        from .services.export import generate_minutes_pdf

        rec = self.get_object()
        try:
            data = generate_minutes_pdf(rec)
        except Exception as exc:  # noqa: BLE001
            logger.exception("export_pdf KO")
            return Response(
                {"detail": f"Erreur génération PDF : {exc}"},
                status=500,
            )

        filename = _slug_filename(rec, "pdf")
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


def _slug_filename(rec, ext: str) -> str:
    """Génère un nom de fichier propre depuis le titre de la réunion."""
    import re
    title = (getattr(rec.meeting, "title", "") or "compte-rendu").strip()
    slug = re.sub(r"[^A-Za-z0-9_\- ]", "", title).strip().replace(" ", "_")[:80]
    date = ""
    if getattr(rec.meeting, "scheduled_start", None):
        date = rec.meeting.scheduled_start.strftime("_%Y-%m-%d")
    return f"CR_{slug}{date}.{ext}"


# ─── Chunked upload : 4 endpoints ───────────────────────────────
#
# Flux client :
#   1. POST   /meetings/{meeting_id}/recordings/upload/init/
#         → { recording_id, chunk_size_bytes, total_chunks }
#   2. PUT    /recordings/upload/{recording_id}/chunks/{index}/  (multipart)
#         → { uploaded_chunks: [0,1,2,...] }
#         (envoyés en parallèle par le client — pool de 4)
#   3. GET    /recordings/upload/{recording_id}/status/
#         → état complet (pour reprise après coupure)
#   4. POST   /recordings/upload/{recording_id}/complete/
#         → MeetingRecording final + pipeline Celery déclenché

def init_chunked(request, meeting_id):
    """POST /meetings/{meeting_id}/recordings/upload/init/"""
    from .serializers import InitChunkedUploadSerializer
    from .services.chunked_upload import init_chunked_upload, DEFAULT_CHUNK_SIZE_BYTES

    if request.method != "POST":
        return Response({"detail": "Méthode non autorisée"}, status=405)
    if not request.user.is_authenticated:
        return Response({"detail": "Authentification requise"}, status=401)

    # Vérification accès / tenant via CanRecordOnMeeting (logique réutilisée)
    perm = CanRecordOnMeeting()
    # Construit un faux view pour la perm
    class _V:
        kwargs = {"meeting_id": meeting_id}
    if not perm.has_permission(request, _V()):
        return Response({"detail": str(getattr(perm, "message", "Refusé."))}, status=403)

    meeting = _get_meeting_or_404(meeting_id)
    ser = InitChunkedUploadSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        rec, chunk_size, total_chunks = init_chunked_upload(
            meeting=meeting,
            recorded_by=request.user,
            filename=ser.validated_data["filename"],
            total_size_bytes=ser.validated_data["total_size_bytes"],
            content_type=ser.validated_data.get("content_type", ""),
            chunk_size_bytes=ser.validated_data.get(
                "chunk_size_bytes", DEFAULT_CHUNK_SIZE_BYTES,
            ),
            title=ser.validated_data.get("title", ""),
            duration_seconds=ser.validated_data.get("duration_seconds"),
            consent_acknowledged=ser.validated_data.get("consent_acknowledged", False),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        logger.exception("init_chunked KO meeting=%s", meeting_id)
        return Response(
            {"detail": f"Impossible d'initialiser l'upload : {exc}"},
            status=500,
        )

    return Response(
        {
            "recording_id": str(rec.id),
            "chunk_size_bytes": chunk_size,
            "total_chunks": total_chunks,
            "expected_total_bytes": rec.file_size,
        },
        status=status.HTTP_201_CREATED,
    )


def upload_chunk(request, recording_id, chunk_index):
    """PUT /recordings/upload/{recording_id}/chunks/{chunk_index}/

    Body : binaire (multipart `chunk` field).
    """
    from .serializers import ChunkUploadSerializer
    from .services.chunked_upload import save_chunk

    if request.method != "PUT":
        return Response({"detail": "Méthode non autorisée"}, status=405)
    if not request.user.is_authenticated:
        return Response({"detail": "Authentification requise"}, status=401)

    rec = MeetingRecording.unscoped.filter(id=recording_id).first()
    if rec is None:
        return Response({"detail": "Enregistrement introuvable"}, status=404)

    # Vérif tenant manuelle
    from apps.accounts.models import Membership
    ok = Membership.unscoped.filter(
        user=request.user, organization=rec.organization, is_active=True,
    ).exists()
    if not ok:
        return Response(
            {"detail": "Vous n'êtes pas membre de cette organisation."},
            status=403,
        )

    ser = ChunkUploadSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        chunk = save_chunk(
            recording=rec,
            chunk_index=int(chunk_index),
            chunk_file=ser.validated_data["chunk"],
            expected_size=ser.validated_data.get("expected_size"),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "upload_chunk KO rec=%s idx=%s", recording_id, chunk_index,
        )
        return Response(
            {"detail": f"Erreur sauvegarde chunk : {exc}"},
            status=502,
        )

    # On renvoie un payload léger : ce chunk + liste des indices déjà reçus.
    received = list(
        RecordingChunk.unscoped
        .filter(recording=rec)
        .order_by("index")
        .values_list("index", flat=True)
    )
    return Response(
        {
            "recording_id": str(rec.id),
            "chunk_index": chunk.index,
            "size": chunk.size,
            "checksum": chunk.checksum,
            "uploaded_chunks": received,
            "uploaded_count": len(received),
        },
        status=status.HTTP_200_OK,
    )


def get_chunked_status(request, recording_id):
    """GET /recordings/upload/{recording_id}/status/"""
    from .services.chunked_upload import get_upload_status

    if request.method != "GET":
        return Response({"detail": "Méthode non autorisée"}, status=405)
    if not request.user.is_authenticated:
        return Response({"detail": "Authentification requise"}, status=401)

    rec = MeetingRecording.unscoped.filter(id=recording_id).first()
    if rec is None:
        return Response({"detail": "Enregistrement introuvable"}, status=404)

    from apps.accounts.models import Membership
    ok = Membership.unscoped.filter(
        user=request.user, organization=rec.organization, is_active=True,
    ).exists()
    if not ok:
        return Response({"detail": "Accès refusé"}, status=403)

    return Response(get_upload_status(rec), status=status.HTTP_200_OK)


def complete_chunked(request, recording_id):
    """POST /recordings/upload/{recording_id}/complete/"""
    from .serializers import CompleteChunkedUploadSerializer
    from .services.chunked_upload import finalize_chunked_upload

    if request.method != "POST":
        return Response({"detail": "Méthode non autorisée"}, status=405)
    if not request.user.is_authenticated:
        return Response({"detail": "Authentification requise"}, status=401)

    rec = MeetingRecording.unscoped.filter(id=recording_id).first()
    if rec is None:
        return Response({"detail": "Enregistrement introuvable"}, status=404)

    from apps.accounts.models import Membership
    ok = Membership.unscoped.filter(
        user=request.user, organization=rec.organization, is_active=True,
    ).exists()
    if not ok:
        return Response({"detail": "Accès refusé"}, status=403)

    ser = CompleteChunkedUploadSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        rec = finalize_chunked_upload(
            recording=rec,
            total_chunks=ser.validated_data["total_chunks"],
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        logger.exception("complete_chunked KO rec=%s", recording_id)
        return Response(
            {"detail": f"Erreur finalisation : {exc}"},
            status=502,
        )

    return Response(
        MeetingRecordingDetailSerializer(rec, context={"request": request}).data,
        status=status.HTTP_202_ACCEPTED,
    )


# Wrappers DRF function-based pour brancher dans urls.py
from rest_framework.decorators import (
    api_view, parser_classes as _parser_classes, permission_classes as _permission_classes,
)


@api_view(["POST"])
@_parser_classes([JSONParser])
@_permission_classes([IsAuthenticated])
def chunked_upload_init_view(request, meeting_id):
    return init_chunked(request, meeting_id)


@api_view(["PUT"])
@_parser_classes([MultiPartParser, FormParser])
@_permission_classes([IsAuthenticated])
def chunked_upload_chunk_view(request, recording_id, chunk_index):
    return upload_chunk(request, recording_id, chunk_index)


@api_view(["GET"])
@_permission_classes([IsAuthenticated])
def chunked_upload_status_view(request, recording_id):
    return get_chunked_status(request, recording_id)


@api_view(["POST"])
@_parser_classes([JSONParser])
@_permission_classes([IsAuthenticated])
def chunked_upload_complete_view(request, recording_id):
    return complete_chunked(request, recording_id)
