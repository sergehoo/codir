"""Lot 2 — Agent IA proactif : modèle ProactiveAlert (dédup + métriques)."""
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_engine", "0002_aiactionrequest"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProactiveAlert",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("target_kind", models.CharField(db_index=True, max_length=20)),
                ("target_id", models.CharField(db_index=True, max_length=80)),
                ("reason", models.CharField(max_length=300)),
                ("health_score_at_emit", models.PositiveSmallIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("emitted", "Émis"),
                            ("read", "Lu"),
                            ("dismissed", "Ignoré"),
                        ],
                        default="emitted",
                        max_length=20,
                    ),
                ),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "ai_message",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="proactive_alerts",
                        to="ai_engine.aimessage",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="proactive_alerts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="proactivealert",
            index=models.Index(
                fields=["user", "target_kind", "target_id", "-created_at"],
                name="ai_engine_p_user_id_idx_pa",
            ),
        ),
        migrations.AddIndex(
            model_name="proactivealert",
            index=models.Index(
                fields=["organization", "-created_at"],
                name="ai_engine_p_org_idx_pa",
            ),
        ),
    ]
