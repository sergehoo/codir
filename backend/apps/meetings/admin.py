from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    Meeting, MeetingAttendance, MeetingMinutes,
    MeetingNote, MeetingParticipant, MeetingSeries,
)


@admin.register(MeetingSeries)
class MeetingSeriesAdmin(TenantAwareAdmin):
    list_display = (
        "title", "frequency", "day_of_week", "time",
        "default_chair", "is_active",
        "last_generated_until", "instances_count",
    )
    list_filter = ("frequency", "is_active", "meeting_type")
    search_fields = ("title", "description", "location")
    autocomplete_fields = (
        "organization", "default_chair", "default_secretary", "default_participants",
    )
    readonly_fields = ("last_generated_until", "created_at", "updated_at")
    fieldsets = (
        ("Identité", {"fields": ("organization", "title", "description", "meeting_type")}),
        ("Récurrence", {"fields": (
            "frequency", "day_of_week", "day_of_month", "time", "duration_minutes",
        )}),
        ("Lieu / Lien", {"fields": ("location", "video_url")}),
        ("Défauts copiés à chaque instance", {"fields": (
            "default_chair", "default_secretary", "default_participants",
        )}),
        ("Génération", {"fields": (
            "starts_on", "ends_on", "generate_weeks_ahead",
            "last_generated_until", "is_active",
        )}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Instances")
    def instances_count(self, obj):
        return obj.instances.count()


class MeetingParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "external_email", "external_name", "role", "is_required", "invited_at")
    readonly_fields = ("invited_at",)


class MeetingAttendanceInline(admin.TabularInline):
    model = MeetingAttendance
    extra = 0
    autocomplete_fields = ("participant", "recorded_by")
    fields = ("participant", "status", "arrived_at", "left_at", "comment")


@admin.register(Meeting)
class MeetingAdmin(TenantAwareAdmin):
    list_display = (
        "title", "meeting_type", "status",
        "scheduled_start", "scheduled_end",
        "chair", "secretary", "quorum_reached", "organization",
    )
    list_filter = ("status", "meeting_type", "quorum_reached", "organization")
    search_fields = ("title", "description", "location")
    autocomplete_fields = ("chair", "secretary", "created_by", "organization", "minutes_doc")
    readonly_fields = ("id", "created_at", "updated_at", "actual_start", "actual_end", "minutes_generated_at")
    inlines = [MeetingParticipantInline, MeetingAttendanceInline]
    date_hierarchy = "scheduled_start"
    fieldsets = (
        ("Identité", {"fields": ("id", "title", "description", "meeting_type", "organization")}),
        ("Planning", {"fields": ("scheduled_start", "scheduled_end", "actual_start", "actual_end",
                                  "location", "video_url")}),
        ("État", {"fields": ("status", "quorum_min", "quorum_reached")}),
        ("Pilotage", {"fields": ("chair", "secretary", "created_by")}),
        ("Compte rendu", {"fields": ("final_notes_md", "minutes_doc", "minutes_generated_at")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(TenantAwareAdmin):
    list_display = ("meeting", "user", "external_email", "role", "is_required", "invited_at")
    list_filter = ("role", "is_required")
    search_fields = ("meeting__title", "user__email", "external_email", "external_name")
    autocomplete_fields = ("meeting", "user")


@admin.register(MeetingAttendance)
class MeetingAttendanceAdmin(TenantAwareAdmin):
    list_display = ("meeting", "participant", "status", "arrived_at", "left_at", "recorded_by")
    list_filter = ("status",)
    search_fields = ("meeting__title",)
    autocomplete_fields = ("meeting", "participant", "recorded_by")


@admin.register(MeetingNote)
class MeetingNoteAdmin(TenantAwareAdmin):
    list_display = ("meeting", "author", "is_private", "created_at")
    list_filter = ("is_private",)
    search_fields = ("meeting__title", "content_md")
    autocomplete_fields = ("meeting", "author")


@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(TenantAwareAdmin):
    list_display = ("meeting", "title", "generated_by", "created_at")
    search_fields = ("meeting__title", "title")
    autocomplete_fields = ("meeting", "generated_by", "document")
    readonly_fields = ("created_at", "updated_at")
