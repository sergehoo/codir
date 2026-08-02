"""Serializers DRF — meeting_recordings.

Convention :
- *ListSerializer : version légère (list endpoints, polling status).
- *DetailSerializer : version riche (avec transcript + speakers + extractions).
- *UploadSerializer : payload d'upload (multipart).
- Speakers, mappings, extractions : serializers dédiés.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    AIExtractionStatus, AIExtractionType,
    DetectedSpeaker, MeetingRecording, RecordingAIExtraction,
    RecordingChunk, RecordingMinutesVersion,
    SpeakerParticipantMapping, SpeakerSegment,
)


# ─── Sous-objets ───────────────────────────────────────────────

class _UserMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return (" ".join(filter(None, [obj.first_name, obj.last_name])) or obj.email)


class SpeakerSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeakerSegment
        fields = ("id", "speaker_label", "start_time", "end_time",
                  "text", "confidence", "audio_excerpt")
        read_only_fields = fields


class DetectedSpeakerSerializer(serializers.ModelSerializer):
    sample_audio_url = serializers.SerializerMethodField()
    suggested_participant = _UserMiniSerializer(read_only=True)
    mapped_participant = _UserMiniSerializer(read_only=True)

    class Meta:
        model = DetectedSpeaker
        fields = (
            "id", "speaker_label", "display_name", "sample_audio",
            "sample_audio_url", "total_segments", "total_duration",
            "confidence", "suggested_participant", "mapped_participant",
            "is_confirmed", "voice_match_confidence",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "speaker_label", "total_segments",
                            "total_duration", "confidence",
                            "voice_match_confidence",
                            "created_at", "updated_at", "sample_audio_url")

    def get_sample_audio_url(self, obj):
        """URL de stream Django avec token signé éphémère (?token=...).

        Le token signé permet à la balise HTML <audio src=...> d'accéder
        au fichier sans header Authorization (impossible côté <audio>).
        Validité : 30 min, lié au path + user → impossible à réutiliser.
        """
        if not obj.sample_audio:
            return None
        from .audio_tokens import generate_audio_token
        request = self.context.get("request")
        path = f"/api/v1/recordings/{obj.recording_id}/speakers/{obj.speaker_label}/sample/"
        user_id = getattr(getattr(request, "user", None), "id", "anon")
        token = generate_audio_token(
            resource_path=path, user_id=user_id, expiry_seconds=30 * 60,
        )
        full_path = f"{path}?token={token}"
        if request is not None:
            return request.build_absolute_uri(full_path)
        return full_path


class SpeakerMappingInputSerializer(serializers.Serializer):
    """Payload de l'endpoint POST /speaker-mapping/ pour 1 voix."""
    speaker_label = serializers.CharField(max_length=40)
    participant_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=300)


class BulkSpeakerMappingInputSerializer(serializers.Serializer):
    """Payload bulk : mappe plusieurs voix d'un coup (confirm-speakers)."""
    mappings = SpeakerMappingInputSerializer(many=True)


class SpeakerParticipantMappingSerializer(serializers.ModelSerializer):
    participant = _UserMiniSerializer(read_only=True)
    confirmed_by = _UserMiniSerializer(read_only=True)

    class Meta:
        model = SpeakerParticipantMapping
        fields = ("id", "speaker_label", "participant", "confirmed_by",
                  "confirmed_at", "confidence", "notes")
        read_only_fields = fields


class RecordingAIExtractionSerializer(serializers.ModelSerializer):
    validated_by = _UserMiniSerializer(read_only=True)

    class Meta:
        model = RecordingAIExtraction
        fields = (
            "id", "extraction_type", "raw_payload", "status",
            "created_decision", "created_action_plan",
            "validation_status", "validated_by", "validated_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "extraction_type", "created_decision",
                            "created_action_plan", "validated_by",
                            "validated_at", "created_at", "updated_at")


# ─── MeetingRecording — list / detail / upload ─────────────────

class MeetingRecordingListSerializer(serializers.ModelSerializer):
    """Version légère utilisée pour la liste + le polling de statut.

    Lot HIST : expose de quoi construire une liste d'historique riche
    (aperçu du CR, nb de versions, état d'archivage) sans avoir à faire
    un appel /detail/ par enregistrement.
    """

    recorded_by = _UserMiniSerializer(read_only=True)
    audio_url = serializers.SerializerMethodField()
    has_summary = serializers.SerializerMethodField()
    summary_preview = serializers.SerializerMethodField()
    versions_count = serializers.SerializerMethodField()
    has_audio = serializers.SerializerMethodField()

    class Meta:
        model = MeetingRecording
        fields = (
            "id", "meeting", "title", "status", "recorded_by",
            "duration_seconds", "file_size", "mime_type", "audio_url",
            "started_at", "stopped_at", "uploaded_at",
            "processing_started_at", "processing_finished_at",
            "error_message", "created_at", "updated_at",
            # ── Lot HIST ──
            "has_summary", "summary_preview", "versions_count", "has_audio",
            "is_archived", "archived_at", "internal_note",
        )

    def get_has_summary(self, obj) -> bool:
        return bool((obj.ai_minutes or "").strip() or (obj.summary or "").strip())

    def get_summary_preview(self, obj) -> str:
        """Premiers caractères du CR, nettoyés du Markdown le plus bruyant."""
        raw = (obj.summary or obj.ai_minutes or "").strip()
        if not raw:
            return ""
        # Retire les titres Markdown et les puces pour un aperçu lisible.
        lines = [
            ln.strip().lstrip("#").lstrip("*-").strip()
            for ln in raw.splitlines()
            if ln.strip() and not ln.strip().startswith("---")
        ]
        text = " ".join(lines)
        return text[:220] + ("…" if len(text) > 220 else "")

    def get_versions_count(self, obj) -> int:
        # Utilise le prefetch si présent, sinon compte (liste bornée à 50).
        cached = getattr(obj, "_prefetched_objects_cache", {}) or {}
        if "minutes_versions" in cached:
            return len(cached["minutes_versions"])
        return obj.minutes_versions.count()

    def get_has_audio(self, obj) -> bool:
        return bool(obj.audio_file) and obj.deleted_audio_at is None

    def get_audio_url(self, obj):
        """URL de stream Django avec token signé éphémère (?token=...).

        Endpoint : GET /api/v1/recordings/{id}/audio/?token=...
        Le token permet la lecture par <audio> sans Authorization header.
        """
        if not obj.audio_file:
            return None
        from .audio_tokens import generate_audio_token
        request = self.context.get("request")
        path = f"/api/v1/recordings/{obj.id}/audio/"
        user_id = getattr(getattr(request, "user", None), "id", "anon")
        token = generate_audio_token(
            resource_path=path, user_id=user_id, expiry_seconds=30 * 60,
        )
        full_path = f"{path}?token={token}"
        if request is not None:
            return request.build_absolute_uri(full_path)
        return full_path


class MeetingRecordingDetailSerializer(MeetingRecordingListSerializer):
    """Detail : transcripts + speakers + extractions."""

    speakers = DetectedSpeakerSerializer(many=True, read_only=True)
    extractions = RecordingAIExtractionSerializer(many=True, read_only=True)
    segments_count = serializers.SerializerMethodField()

    class Meta(MeetingRecordingListSerializer.Meta):
        fields = MeetingRecordingListSerializer.Meta.fields + (
            "transcript_raw", "transcript_with_speakers", "transcript_final",
            "summary", "ai_minutes", "speakers", "extractions",
            "segments_count", "consent_acknowledged_at",
        )

    def get_segments_count(self, obj):
        return obj.segments.count()


# ─── Historisation du compte rendu (lot HIST) ──────────────────

class MinutesVersionListSerializer(serializers.ModelSerializer):
    """Entrée d'historique — sans le contenu complet (payload léger)."""

    created_by = _UserMiniSerializer(read_only=True)
    origin_display = serializers.CharField(source="get_origin_display", read_only=True)
    char_count = serializers.IntegerField(read_only=True)
    restored_from_version = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()

    class Meta:
        model = RecordingMinutesVersion
        fields = (
            "id", "version_number", "origin", "origin_display", "label",
            "created_by", "created_at", "char_count",
            "restored_from_version", "preview",
        )
        read_only_fields = fields

    def get_restored_from_version(self, obj):
        return obj.restored_from.version_number if obj.restored_from_id else None

    def get_preview(self, obj) -> str:
        raw = (obj.summary or obj.ai_minutes or "").strip()
        lines = [
            ln.strip().lstrip("#").lstrip("*-").strip()
            for ln in raw.splitlines()
            if ln.strip() and not ln.strip().startswith("---")
        ]
        text = " ".join(lines)
        return text[:180] + ("…" if len(text) > 180 else "")


class MinutesVersionDetailSerializer(MinutesVersionListSerializer):
    """Version complète — inclut le Markdown intégral pour consultation."""

    class Meta(MinutesVersionListSerializer.Meta):
        fields = MinutesVersionListSerializer.Meta.fields + (
            "summary", "ai_minutes",
        )
        read_only_fields = fields


class UpdateRecordingMetaSerializer(serializers.Serializer):
    """PATCH /recordings/{id}/meta/ — renommer / annoter un enregistrement."""

    title = serializers.CharField(
        max_length=250, required=False, allow_blank=True,
    )
    internal_note = serializers.CharField(
        max_length=5000, required=False, allow_blank=True,
    )


class StartRecordingSerializer(serializers.Serializer):
    """POST /meetings/{id}/recordings/start/"""
    title = serializers.CharField(max_length=250, required=False, allow_blank=True)
    consent_acknowledged = serializers.BooleanField(default=False)
    skip_speaker_detection = serializers.BooleanField(default=False)


class InitChunkedUploadSerializer(serializers.Serializer):
    """POST /meetings/{id}/recordings/upload/init/ — démarre un upload chunked.

    Le client annonce filename + taille totale ; le serveur retourne :
      - recording_id (UUID)
      - chunk_size_bytes (taille des chunks à utiliser)
      - total_chunks (combien de PUT attendus)
    """
    filename = serializers.CharField(max_length=300)
    total_size_bytes = serializers.IntegerField(min_value=1)
    content_type = serializers.CharField(max_length=80, required=False, allow_blank=True)
    chunk_size_bytes = serializers.IntegerField(
        min_value=1024 * 1024,  # 1 Mo
        max_value=100 * 1024 * 1024,  # 100 Mo
        required=False,
    )
    title = serializers.CharField(max_length=250, required=False, allow_blank=True)
    duration_seconds = serializers.FloatField(required=False, min_value=0)
    consent_acknowledged = serializers.BooleanField(default=False)
    skip_speaker_detection = serializers.BooleanField(default=False)

    def validate_total_size_bytes(self, value):
        from django.conf import settings
        max_mb = getattr(settings, "MAX_RECORDING_UPLOAD_MB", 600)
        if value > max_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"Fichier trop volumineux ({value / 1024 / 1024:.1f} Mo). "
                f"Limite : {max_mb} Mo.",
            )
        return value


class ChunkUploadSerializer(serializers.Serializer):
    """PUT /recordings/upload/{rec_id}/chunks/{index}/ — chunk binaire."""
    chunk = serializers.FileField()
    expected_size = serializers.IntegerField(required=False, min_value=0)


class CompleteChunkedUploadSerializer(serializers.Serializer):
    """POST /recordings/upload/{rec_id}/complete/ — finalise."""
    total_chunks = serializers.IntegerField(min_value=1)


class UploadRecordingSerializer(serializers.Serializer):
    """POST /meetings/{id}/recordings/upload/ — multipart.

    Si `recording_id` est fourni, on remplit un enregistrement créé via /start/.
    Sinon, on en crée un à la volée (cas mobile / fast-path).
    """
    recording_id = serializers.UUIDField(required=False)
    audio = serializers.FileField()
    title = serializers.CharField(max_length=250, required=False, allow_blank=True)
    duration_seconds = serializers.FloatField(required=False, min_value=0)
    consent_acknowledged = serializers.BooleanField(default=False)
    skip_speaker_detection = serializers.BooleanField(default=False)

    def validate_audio(self, value):
        from django.conf import settings
        max_mb = getattr(settings, "MAX_RECORDING_UPLOAD_MB", 600)
        max_bytes = max_mb * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"Fichier trop volumineux ({value.size / 1024 / 1024:.1f} Mo). "
                f"Limite : {max_mb} Mo.",
            )
        # Validation MIME tolérante : on accepte audio/* (mp3, m4a, wav, aac,
        # ogg, opus, flac, webm…), video/webm et video/mp4 (souvent contenant
        # de l'audio AAC), et application/octet-stream (Firefox/Safari
        # peuvent envoyer ça pour des fichiers locaux sans MIME connu).
        # En dernier recours, on tolère un content_type vide — le pipeline
        # détectera le format réel via ffmpeg / AssemblyAI plus tard.
        allowed_prefixes = (
            "audio/", "video/webm", "video/mp4", "video/mpeg",
            "application/octet-stream", "application/ogg",
        )
        ctype = (value.content_type or "").lower()
        if ctype and not any(ctype.startswith(p) for p in allowed_prefixes):
            raise serializers.ValidationError(
                f"Type MIME non supporté : {ctype}. "
                "Formats acceptés : mp3, m4a, wav, aac, ogg, opus, flac, webm, mp4.",
            )
        return value


class ValidateExtractionSerializer(serializers.Serializer):
    """POST /recordings/{id}/create-decisions/ et /create-action-plans/.

    Liste d'IDs d'extractions à pousser dans les modules cibles.
    """
    extraction_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False,
    )
