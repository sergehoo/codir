"""Smart meeting notes : versionning + détection décisions/actions/mentions."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DETECTED_STATUS = [
    ("pending", "En attente"),
    ("published", "Publiée"),
    ("dismissed", "Rejetée"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("meetings", "0001_initial"),
        ("decisions", "0001_initial"),
        ("action_plans", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ─── MeetingNote : extension ─────────────────────────
        migrations.AlterField(
            model_name="meetingnote",
            name="content_md",
            field=models.TextField(blank=True, help_text="Texte plat exporté (legacy / fallback)."),
        ),
        migrations.AddField(
            model_name="meetingnote",
            name="content_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="meetingnote",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="meetingnote",
            name="is_current",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="meetingnote",
            name="last_autosaved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="meetingnote",
            options={"ordering": ["-version", "-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="meetingnote",
            index=models.Index(fields=["meeting", "is_current"], name="mtg_note_curr_idx"),
        ),
        migrations.AddIndex(
            model_name="meetingnote",
            index=models.Index(fields=["meeting", "-version"], name="mtg_note_ver_idx"),
        ),

        # ─── MeetingDetectedDecision ──────────────────────────
        migrations.CreateModel(
            name="MeetingDetectedDecision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=400)),
                ("raw_line", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=DETECTED_STATUS, default="pending", max_length=12)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("decision", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="detected_source",
                    to="decisions.decision",
                )),
                ("meeting", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="detected_decisions",
                    to="meetings.meeting",
                )),
                ("note", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="detected_decisions",
                    to="meetings.meetingnote",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+",
                    to="organizations.organization",
                )),
                ("published_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="decisions_published",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["meeting", "order"],
                "indexes": [models.Index(fields=["meeting", "status"], name="mtg_dd_status_idx")],
            },
        ),

        # ─── MeetingDetectedAction ───────────────────────────
        migrations.CreateModel(
            name="MeetingDetectedAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=400)),
                ("raw_line", models.TextField(blank=True)),
                ("assignee_mention", models.CharField(blank=True, max_length=200)),
                ("order", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=DETECTED_STATUS, default="pending", max_length=12)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("action_task", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="detected_source",
                    to="action_plans.actiontask",
                )),
                ("assignee", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="detected_action_assignments",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("detected_decision", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="actions",
                    to="meetings.meetingdetecteddecision",
                )),
                ("meeting", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="detected_actions",
                    to="meetings.meeting",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+",
                    to="organizations.organization",
                )),
                ("published_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="actions_published",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["meeting", "order"],
                "indexes": [
                    models.Index(fields=["meeting", "status"], name="mtg_da_status_idx"),
                    models.Index(fields=["detected_decision"], name="mtg_da_dd_idx"),
                ],
            },
        ),

        # ─── MeetingMention ──────────────────────────────────
        migrations.CreateModel(
            name="MeetingMention",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("raw_text", models.CharField(max_length=200)),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("meeting", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mentions",
                    to="meetings.meeting",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+",
                    to="organizations.organization",
                )),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="meeting_mentions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["meeting", "-occurrences"],
                "indexes": [models.Index(fields=["meeting", "user"], name="mtg_mention_user_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("meeting", "user"),
                        condition=models.Q(("user__isnull", False)),
                        name="uniq_meeting_user_mention",
                    ),
                ],
            },
        ),
    ]
