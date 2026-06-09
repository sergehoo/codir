# Migration : ajout de VoiceProfile + VoiceProfileSample + champ
# voice_match_confidence sur DetectedSpeaker.
#
# Permet la reconnaissance vocale incrémentale : chaque mapping confirmé
# enrichit le profil vocal du user, et les diarisations futures matchent
# automatiquement les voix connues.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meeting_recordings", "0002_meetingrecording_skip_speaker_detection"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Champ confidence sur DetectedSpeaker ──
        migrations.AddField(
            model_name="detectedspeaker",
            name="voice_match_confidence",
            field=models.FloatField(
                default=0.0,
                help_text=(
                    "Score de matching avec un VoiceProfile existant (0..1). "
                    "0 = pas de match au-dessus du seuil. > 0.75 = match confiant."
                ),
            ),
        ),
        # ── VoiceProfile ──
        migrations.CreateModel(
            name="VoiceProfile",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("sample_count", models.PositiveIntegerField(default=0)),
                ("last_updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="voice_profiles", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["user_id"],
                "indexes": [
                    models.Index(
                        fields=["organization", "is_active"],
                        name="voice_profil_organiz_8e6cb6_idx",
                    ),
                ],
                "unique_together": {("organization", "user")},
            },
        ),
        # ── VoiceProfileSample ──
        migrations.CreateModel(
            name="VoiceProfileSample",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_speaker_label", models.CharField(blank=True, max_length=40)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("quality_score", models.FloatField(default=1.0)),
                ("added_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="voice_samples_added", to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
                ("source_recording", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="voice_samples_contributed",
                    to="meeting_recordings.meetingrecording",
                )),
                ("voice_profile", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="samples",
                    to="meeting_recordings.voiceprofile",
                )),
            ],
            options={
                "ordering": ["voice_profile_id", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["voice_profile", "-created_at"],
                        name="voice_profil_voice_p_a2c1f4_idx",
                    ),
                ],
            },
        ),
    ]
