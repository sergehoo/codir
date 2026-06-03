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
    RecordingChunk, SpeakerParticipantMapping, SpeakerSegment,
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
            "is_confirmed", "created_at", "updated_at",
        )
        read_only_fields = ("id", "speaker_label", "total_segments",
                            "total_duration", "confidence", "created_at",
                            "updated_at", "sample_audio_url")

    def get_sample_audio_url(self, obj):
        """URL de stream Django (et NON MinIO public).

        On retourne une URL `/api/v1/recordings/{rec_id}/speakers/{label}/sample/`
        servie par Django qui re-stream le fichier depuis le storage interne.
        Avantages : auth + permissions DRF, pas de dépendance DNS/cert MinIO public,
        pas de problème de signature/expiration.
        """
        if not obj.sample_audio:
            return None
        request = self.context.get("request")
        path = f"/api/v1/recordings/{obj.recording_id}/speakers/{obj.speaker_label}/sample/"
        if request is not None:
            return request.build_absolute_uri(path)
        return path


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
    """Version légère utilisée pour la liste + le polling de statut."""

    recorded_by = _UserMiniSerializer(read_only=True)
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = MeetingRecording
        fields = (
            "id", "meeting", "title", "status", "recorded_by",
            "duration_seconds", "file_size", "mime_type", "audio_url",
            "started_at", "stopped_at", "uploaded_at",
            "processing_started_at", "processing_finished_at",
            "error_message", "created_at", "updated_at",
        )

    def get_audio_url(self, obj):
        """URL de stream Django pour l'audio complet (pas MinIO public).

        Endpoint : GET /api/v1/recordings/{id}/audio/
        Sécurisé par DRF (auth + CanAccessMeetingRecording) ; pas besoin
        que MinIO soit publiquement accessible.
        """
        if not obj.audio_file:
            return None
        request = self.context.get("request")
        path = f"/api/v1/recordings/{obj.id}/audio/"
        if request is not None:
            return request.build_absolute_uri(path)
        return path


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


class StartRecordingSerializer(serializers.Serializer):
    """POST /meetings/{id}/recordings/start/"""
    title = serializers.CharField(max_length=250, required=False, allow_blank=True)
    consent_acknowledged = serializers.BooleanField(default=False)


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

    def validate_audio(self, value):
        from django.conf import settings
        max_mb = getattr(settings, "MAX_RECORDING_UPLOAD_MB", 600)
        max_bytes = max_mb * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"Fichier trop volumineux ({value.size / 1024 / 1024:.1f} Mo). "
                f"Limite : {max_mb} Mo.",
            )
        allowed_prefixes = ("audio/", "video/webm", "video/mp4")  # webm peut être audio
        ctype = (value.content_type or "").lower()
        if ctype and not any(ctype.startswith(p) for p in allowed_prefixes):
            raise serializers.ValidationError(
                f"Type MIME non supporté : {ctype}. Attendu : audio/* ou video/webm.",
            )
        return value


class ValidateExtractionSerializer(serializers.Serializer):
    """POST /recordings/{id}/create-decisions/ et /create-action-plans/.

    Liste d'IDs d'extractions à pousser dans les modules cibles.
    """
    extraction_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False,
    )
