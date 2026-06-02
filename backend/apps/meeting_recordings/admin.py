"""Admin Django pour meeting_recordings — diagnostic & contrôle qualité."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    DetectedSpeaker, MeetingRecording, RecordingAIExtraction, RecordingChunk,
    SpeakerParticipantMapping, SpeakerSegment,
)


@admin.register(MeetingRecording)
class MeetingRecordingAdmin(TenantAwareAdmin):
    list_display = (
        "id", "meeting", "status", "recorded_by",
        "duration_seconds", "file_size", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "meeting__title", "recorded_by__email")
    readonly_fields = (
        "id", "created_at", "updated_at", "uploaded_at",
        "processing_started_at", "processing_finished_at",
    )
    ordering = ("-created_at",)


@admin.register(RecordingChunk)
class RecordingChunkAdmin(TenantAwareAdmin):
    list_display = ("id", "recording", "index", "start_time", "end_time", "size", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("recording__id",)
    ordering = ("recording", "index")


@admin.register(SpeakerSegment)
class SpeakerSegmentAdmin(TenantAwareAdmin):
    list_display = ("id", "recording", "speaker_label", "start_time", "end_time", "confidence")
    list_filter = ("speaker_label",)
    search_fields = ("recording__id", "speaker_label", "text")
    ordering = ("recording", "start_time")


@admin.register(DetectedSpeaker)
class DetectedSpeakerAdmin(TenantAwareAdmin):
    list_display = (
        "id", "recording", "speaker_label", "display_name",
        "total_duration", "total_segments", "mapped_participant", "is_confirmed",
    )
    list_filter = ("is_confirmed",)
    search_fields = ("recording__id", "speaker_label", "display_name",
                     "mapped_participant__email")
    ordering = ("recording", "speaker_label")


@admin.register(SpeakerParticipantMapping)
class SpeakerParticipantMappingAdmin(TenantAwareAdmin):
    list_display = ("id", "recording", "speaker_label", "participant",
                    "confirmed_by", "confirmed_at", "confidence")
    list_filter = ("confirmed_at",)
    search_fields = ("recording__id", "speaker_label",
                     "participant__email", "confirmed_by__email")
    ordering = ("-confirmed_at",)


@admin.register(RecordingAIExtraction)
class RecordingAIExtractionAdmin(TenantAwareAdmin):
    list_display = (
        "id", "recording", "extraction_type", "status",
        "created_decision", "created_action_plan", "validated_by", "validated_at",
    )
    list_filter = ("extraction_type", "status")
    search_fields = ("recording__id",)
    ordering = ("-created_at",)
