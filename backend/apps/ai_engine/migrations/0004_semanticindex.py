"""Lot 3 — Recherche sémantique : index cross-objets (decision/plan/meeting...).

JSONField pour le vecteur 384-dim — portable, performances suffisantes
jusqu'à ~10k items. Migrable vers pgvector au-delà.
"""
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_engine", "0003_proactivealert"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SemanticIndex",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("decision", "Décision"),
                            ("plan", "Plan d'action"),
                            ("meeting", "Réunion"),
                            ("transcript", "Transcript"),
                            ("document", "Document"),
                        ],
                        db_index=True, max_length=20,
                    ),
                ),
                ("source_id", models.CharField(db_index=True, max_length=80)),
                ("title", models.CharField(max_length=300)),
                ("text", models.TextField()),
                ("text_hash", models.CharField(db_index=True, max_length=64)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("model_version", models.CharField(default="minilm-multi-v1", max_length=80)),
                ("url", models.CharField(blank=True, max_length=300)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterUniqueTogether(
            name="semanticindex",
            unique_together={("source_type", "source_id")},
        ),
        migrations.AddIndex(
            model_name="semanticindex",
            index=models.Index(
                fields=["organization", "source_type"],
                name="ai_eng_si_org_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="semanticindex",
            index=models.Index(
                fields=["organization", "model_version"],
                name="ai_eng_si_org_mver_idx",
            ),
        ),
    ]
