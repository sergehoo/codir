"""Serializers DRF — meetings."""
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer
from .models import (
    Meeting, MeetingAttendance, MeetingMinutes,
    MeetingParticipant, MeetingNote, MeetingSeries,
)


class MeetingSeriesSerializer(serializers.ModelSerializer):
    """Sérialise un template de série récurrente."""
    default_chair_detail = UserMiniSerializer(source="default_chair", read_only=True)
    default_secretary_detail = UserMiniSerializer(source="default_secretary", read_only=True)
    default_participants_detail = UserMiniSerializer(
        source="default_participants", many=True, read_only=True,
    )
    instances_count = serializers.SerializerMethodField()
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)
    day_of_week_display = serializers.CharField(source="get_day_of_week_display", read_only=True)

    def get_instances_count(self, obj) -> int:
        return obj.instances.count()

    class Meta:
        model = MeetingSeries
        fields = [
            "id", "title", "description",
            "frequency", "frequency_display",
            "day_of_week", "day_of_week_display",
            "day_of_month", "time", "duration_minutes",
            "meeting_type", "location", "video_url",
            "default_chair", "default_chair_detail",
            "default_secretary", "default_secretary_detail",
            "default_participants", "default_participants_detail",
            "generate_weeks_ahead", "last_generated_until",
            "is_active", "starts_on", "ends_on",
            "instances_count", "created_at", "updated_at",
        ]
        read_only_fields = ("id", "last_generated_until", "created_at", "updated_at")


class MeetingParticipantSerializer(serializers.ModelSerializer):
    user_detail = UserMiniSerializer(source="user", read_only=True)

    class Meta:
        model = MeetingParticipant
        fields = [
            "id", "meeting", "user", "user_detail",
            "external_email", "external_name",
            "role", "is_required", "invited_at",
        ]
        read_only_fields = ("invited_at", "meeting")

    def validate(self, attrs):
        if not attrs.get("user") and not attrs.get("external_email"):
            raise serializers.ValidationError(
                "user ou external_email est requis."
            )
        return attrs


class MeetingAttendanceSerializer(serializers.ModelSerializer):
    participant_detail = MeetingParticipantSerializer(source="participant", read_only=True)

    class Meta:
        model = MeetingAttendance
        fields = [
            "id", "meeting", "participant", "participant_detail",
            "status", "arrived_at", "left_at", "comment", "recorded_by",
        ]
        read_only_fields = ("meeting", "recorded_by")


class MeetingNoteSerializer(serializers.ModelSerializer):
    author_detail = UserMiniSerializer(source="author", read_only=True)

    class Meta:
        model = MeetingNote
        fields = ["id", "meeting", "author", "author_detail", "content_md", "is_private", "created_at"]
        read_only_fields = ("author", "created_at", "meeting")


class MeetingMinutesSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingMinutes
        fields = ["id", "meeting", "title", "body_html", "body_md", "generated_by", "document", "created_at"]
        read_only_fields = fields


class MeetingListSerializer(serializers.ModelSerializer):
    chair_detail = UserMiniSerializer(source="chair", read_only=True)
    secretary_detail = UserMiniSerializer(source="secretary", read_only=True)
    participants_count = serializers.IntegerField(read_only=True)
    present_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id", "title", "meeting_type", "status",
            "scheduled_start", "scheduled_end",
            "actual_start", "actual_end",
            "location", "video_url",
            "chair", "chair_detail",
            "secretary", "secretary_detail",
            "quorum_min", "quorum_reached",
            "participants_count", "present_count",
            "created_at", "updated_at",
        ]


class MeetingDetailSerializer(MeetingListSerializer):
    participants = MeetingParticipantSerializer(many=True, read_only=True)
    attendances = MeetingAttendanceSerializer(many=True, read_only=True)
    notes = MeetingNoteSerializer(many=True, read_only=True)

    class Meta(MeetingListSerializer.Meta):
        fields = MeetingListSerializer.Meta.fields + [
            "description", "final_notes_md",
            "participants", "attendances", "notes",
            "minutes_generated_at",
        ]


class MeetingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = [
            "title", "description", "meeting_type",
            "scheduled_start", "scheduled_end",
            "location", "video_url",
            "chair", "secretary", "quorum_min",
        ]

    def validate(self, attrs):
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError("scheduled_end doit être après scheduled_start.")
        return attrs


class CancelMeetingSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=400)


class RecordAttendanceSerializer(serializers.Serializer):
    participant = serializers.UUIDField()
    status = serializers.ChoiceField(choices=MeetingAttendance._meta.get_field("status").choices)
    arrived_at = serializers.DateTimeField(required=False, allow_null=True)
