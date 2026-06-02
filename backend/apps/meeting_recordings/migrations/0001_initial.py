# Generated migration for apps.meeting_recordings — initial schema.
# Modèles : MeetingRecording, RecordingChunk, SpeakerSegment, DetectedSpeaker,
# SpeakerParticipantMapping, RecordingAIExtraction.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.meeting_recordings.models as _models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        ("meetings", "0001_initial"),
        ("decisions", "0001_initial"),
        ("action_plans", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ─── MeetingRecording ────────────────────────────────────
        migrations.CreateModel(
            name="MeetingRecording",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(blank=True, max_length=250)),
                ("audio_file", models.FileField(
                    blank=True, max_length=600, null=True,
                    upload_to=_models._audio_upload_path)),
                ("audio_normalized", models.FileField(
                    blank=True, max_length=600, null=True,
                    upload_to=_models._audio_upload_path)),
                ("original_filename", models.CharField(blank=True, max_length=300)),
                ("mime_type", models.CharField(blank=True, max_length=80)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("duration_seconds", models.FloatField(default=0)),
                ("status", models.CharField(
                    choices=[
                        ("created", "Créé"),
                        ("recording", "En cours d'enregistrement"),
                        ("uploading", "Upload en cours"),
                        ("uploaded", "Upload terminé"),
                        ("processing", "Traitement initial"),
                        ("transcribing", "Transcription en cours"),
                        ("diarizing", "Détection des voix"),
                        ("waiting_speaker_mapping", "Attente identification des voix"),
                        ("generating_final_transcript", "Génération transcription finale"),
                        ("summarizing", "Résumé IA en cours"),
                        ("extracting_actions", "Extraction décisions/actions"),
                        ("completed", "Terminé"),
                        ("failed", "Échec"),
                    ],
                    db_index=True, default="created", max_length=40)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
                ("uploaded_at", models.DateTimeField(blank=True, null=True)),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("processing_finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("transcript_raw", models.TextField(blank=True)),
                ("transcript_with_speakers", models.JSONField(blank=True, default=list)),
                ("transcript_final", models.JSONField(blank=True, default=list)),
                ("summary", models.TextField(blank=True)),
                ("ai_minutes", models.TextField(blank=True)),
                ("consent_acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_audio_at", models.DateTimeField(blank=True, null=True)),
                ("meeting", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="recordings", to="meetings.meeting")),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("recorded_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="recordings_made",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["organization", "meeting", "-created_at"],
                                 name="mr_rec_org_meet_idx"),
                    models.Index(fields=["organization", "status"],
                                 name="mr_rec_org_status_idx"),
                    models.Index(fields=["organization", "recorded_by"],
                                 name="mr_rec_org_user_idx"),
                ],
            },
        ),
        # ─── RecordingChunk ──────────────────────────────────────
        migrations.CreateModel(
            name="RecordingChunk",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_file", models.FileField(max_length=600,
                                                upload_to=_models._chunk_upload_path)),
                ("index", models.PositiveIntegerField()),
                ("start_time", models.FloatField(default=0)),
                ("end_time", models.FloatField(default=0)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("checksum", models.CharField(blank=True, max_length=64)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="chunks",
                    to="meeting_recordings.meetingrecording")),
            ],
            options={
                "ordering": ["recording_id", "index"],
                "unique_together": {("recording", "index")},
                "indexes": [models.Index(fields=["recording", "index"],
                                         name="mr_chk_rec_idx")],
            },
        ),
        # ─── SpeakerSegment ──────────────────────────────────────
        migrations.CreateModel(
            name="SpeakerSegment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("speaker_label", models.CharField(db_index=True, max_length=40)),
                ("start_time", models.FloatField()),
                ("end_time", models.FloatField()),
                ("text", models.TextField(blank=True)),
                ("confidence", models.FloatField(default=0)),
                ("audio_excerpt", models.FileField(
                    blank=True, max_length=600, null=True,
                    upload_to=_models._speaker_sample_upload_path)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="segments",
                    to="meeting_recordings.meetingrecording")),
            ],
            options={
                "ordering": ["recording_id", "start_time"],
                "indexes": [
                    models.Index(fields=["recording", "start_time"],
                                 name="mr_seg_rec_start_idx"),
                    models.Index(fields=["recording", "speaker_label"],
                                 name="mr_seg_rec_spk_idx"),
                ],
            },
        ),
        # ─── DetectedSpeaker ─────────────────────────────────────
        migrations.CreateModel(
            name="DetectedSpeaker",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("speaker_label", models.CharField(db_index=True, max_length=40)),
                ("display_name", models.CharField(blank=True, max_length=200)),
                ("sample_audio", models.FileField(
                    blank=True, max_length=600, null=True,
                    upload_to=_models._speaker_sample_upload_path)),
                ("total_segments", models.PositiveIntegerField(default=0)),
                ("total_duration", models.FloatField(default=0)),
                ("confidence", models.FloatField(default=0)),
                ("is_confirmed", models.BooleanField(default=False)),
                ("mapped_participant", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="recording_mappings",
                    to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="speakers",
                    to="meeting_recordings.meetingrecording")),
                ("suggested_participant", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="recording_suggestions",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["recording_id", "speaker_label"],
                "unique_together": {("recording", "speaker_label")},
                "indexes": [
                    models.Index(fields=["recording", "is_confirmed"],
                                 name="mr_dspk_rec_conf_idx"),
                ],
            },
        ),
        # ─── SpeakerParticipantMapping ───────────────────────────
        migrations.CreateModel(
            name="SpeakerParticipantMapping",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("speaker_label", models.CharField(db_index=True, max_length=40)),
                ("confirmed_at", models.DateTimeField(auto_now_add=True)),
                ("confidence", models.FloatField(default=1.0)),
                ("notes", models.CharField(blank=True, max_length=300)),
                ("confirmed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="speaker_mappings_made",
                    to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("participant", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="speaker_mappings",
                    to=settings.AUTH_USER_MODEL)),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mappings",
                    to="meeting_recordings.meetingrecording")),
            ],
            options={
                "ordering": ["recording_id", "-confirmed_at"],
                "indexes": [
                    models.Index(fields=["recording", "speaker_label"],
                                 name="mr_map_rec_spk_idx"),
                    models.Index(fields=["participant"],
                                 name="mr_map_part_idx"),
                ],
            },
        ),
        # ─── RecordingAIExtraction ───────────────────────────────
        migrations.CreateModel(
            name="RecordingAIExtraction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("extraction_type", models.CharField(
                    choices=[
                        ("summary", "Résumé exécutif"),
                        ("minutes", "Compte rendu détaillé"),
                        ("decision", "Décision proposée"),
                        ("action", "Action proposée"),
                        ("risk", "Risque mentionné"),
                        ("deadline", "Échéance détectée"),
                        ("blocker", "Point bloquant"),
                        ("question", "Question reportée"),
                    ],
                    db_index=True, max_length=20)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Brouillon"),
                        ("validated", "Validé"),
                        ("rejected", "Rejeté"),
                        ("pushed", "Poussé dans le module cible"),
                    ],
                    db_index=True, default="draft", max_length=20)),
                ("validation_status", models.CharField(blank=True, max_length=20)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("created_action_plan", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="from_ai_extractions",
                    to="action_plans.actionplan")),
                ("created_decision", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="from_ai_extractions",
                    to="decisions.decision")),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization")),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="extractions",
                    to="meeting_recordings.meetingrecording")),
                ("validated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ai_extractions_validated",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["recording_id", "extraction_type", "-created_at"],
                "indexes": [
                    models.Index(fields=["recording", "extraction_type", "status"],
                                 name="mr_extr_rec_type_idx"),
                    models.Index(fields=["organization", "status"],
                                 name="mr_extr_org_status_idx"),
                ],
            },
        ),
    ]
