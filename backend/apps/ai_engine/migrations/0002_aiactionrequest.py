# Migration : ajout AIActionRequest — actions proposées par l'IA
# en attente de confirmation utilisateur (workflow PENDING → EXECUTED).
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_engine", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AIActionRequest",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action_type", models.CharField(
                    choices=[
                        ("create_decision_draft", "Créer un brouillon de décision"),
                        ("create_action_task",    "Créer une tâche"),
                        ("create_action_plan",    "Créer un plan d'action"),
                        ("assign_task",           "Réassigner une tâche"),
                        ("update_task_status",    "Changer le statut d'une tâche"),
                        ("send_notification",     "Envoyer une notification"),
                    ],
                    db_index=True, max_length=40,
                )),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("summary", models.CharField(blank=True, max_length=400)),
                ("status", models.CharField(
                    choices=[
                        ("pending",   "En attente confirmation"),
                        ("confirmed", "Confirmée par l'utilisateur"),
                        ("executed",  "Exécutée"),
                        ("cancelled", "Annulée"),
                        ("failed",    "Échec d'exécution"),
                    ],
                    db_index=True, default="pending", max_length=20,
                )),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("executed_at",  models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("result_object_type", models.CharField(blank=True, max_length=60)),
                ("result_object_id",   models.CharField(blank=True, max_length=80)),
                ("conversation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="action_requests",
                    to="ai_engine.aiconversation",
                )),
                ("source_message", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="action_requests",
                    to="ai_engine.aimessage",
                )),
                ("requested_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ai_actions_proposed_to",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["conversation", "status"],
                        name="ai_engine_a_convers_stat_idx",
                    ),
                    models.Index(
                        fields=["requested_by", "status"],
                        name="ai_engine_a_user_stat_idx",
                    ),
                ],
            },
        ),
    ]
