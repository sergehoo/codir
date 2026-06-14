# Migration initiale ai_engine — 5 modèles (chat IA + RAG + audit + glossaire).
#
# L'app était présente dans le repo depuis longtemps mais pas dans
# INSTALLED_APPS, donc Django ne créait aucune table. Cette migration crée
# enfin les 5 modèles : AIConversation, AIMessage, AIInferenceLog,
# AIDocumentEmbedding, AIGlossary.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("documents", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── AIConversation ──
        migrations.CreateModel(
            name="AIConversation",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(blank=True, max_length=200)),
                ("context_scope", models.CharField(
                    choices=[
                        ("org", "Organisation"), ("meeting", "Réunion"),
                        ("decision", "Décision"), ("dashboard", "Dashboard"),
                        ("document", "Document"),
                    ],
                    default="org", max_length=20,
                )),
                ("context_id", models.CharField(blank=True, max_length=80)),
                ("is_archived", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ai_conversations", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        # ── AIMessage ──
        migrations.CreateModel(
            name="AIMessage",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(
                    choices=[
                        ("user", "Utilisateur"), ("assistant", "Assistant"),
                        ("system", "Système"), ("tool", "Outil"),
                    ],
                    max_length=10,
                )),
                ("content_md", models.TextField()),
                ("tokens", models.PositiveIntegerField(default=0)),
                ("citations_json", models.JSONField(blank=True, default=list)),
                ("tool_calls_json", models.JSONField(blank=True, default=list)),
                ("feedback", models.SmallIntegerField(blank=True, null=True)),
                ("conversation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="messages", to="ai_engine.aiconversation",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
            ],
            options={"ordering": ["created_at"]},
        ),
        # ── AIInferenceLog ──
        migrations.CreateModel(
            name="AIInferenceLog",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("capability", models.CharField(max_length=40)),
                ("provider", models.CharField(max_length=40)),
                ("model", models.CharField(max_length=80)),
                ("request_hash", models.CharField(db_index=True, max_length=64)),
                ("tokens_in", models.PositiveIntegerField(default=0)),
                ("tokens_out", models.PositiveIntegerField(default=0)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("cost_usd", models.DecimalField(
                    decimal_places=6, default=0, max_digits=10,
                )),
                ("cached", models.BooleanField(default=False)),
                ("success", models.BooleanField(default=True)),
                ("error", models.TextField(blank=True)),
                ("risk_class", models.CharField(default="low", max_length=20)),
                ("actor", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["organization", "-created_at"],
                        name="ai_engine_a_organiz_2af3c1_idx",
                    ),
                    models.Index(
                        fields=["capability", "provider"],
                        name="ai_engine_a_capabil_5d31a7_idx",
                    ),
                ],
            },
        ),
        # ── AIDocumentEmbedding ──
        migrations.CreateModel(
            name="AIDocumentEmbedding",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_index", models.PositiveIntegerField()),
                ("content_text", models.TextField()),
                ("language", models.CharField(default="fr", max_length=10)),
                ("embedding", models.JSONField()),
                ("model_version", models.CharField(max_length=80)),
                ("document", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="embeddings", to="documents.document",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["organization", "document"],
                        name="ai_engine_a_organiz_doc_idx",
                    ),
                    models.Index(
                        fields=["organization", "language"],
                        name="ai_engine_a_organiz_lang_idx",
                    ),
                ],
                "unique_together": {("document", "chunk_index")},
            },
        ),
        # ── AIGlossary ──
        migrations.CreateModel(
            name="AIGlossary",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("term", models.CharField(max_length=120)),
                ("definition", models.TextField()),
                ("aliases", models.JSONField(blank=True, default=list)),
                ("category", models.CharField(blank=True, max_length=40)),
                ("added_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
            ],
            options={
                "ordering": ["term"],
                "unique_together": {("organization", "term")},
            },
        ),
    ]
