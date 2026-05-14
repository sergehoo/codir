"""Migration : extend Notification + add Preference / Log / TaskReminderLog."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


EVENT_CHOICES = [
    ("meeting_invited", "Invitation réunion"),
    ("meeting_reminder", "Rappel réunion"),
    ("meeting_started", "Réunion démarrée"),
    ("meeting_completed", "Réunion clôturée"),
    ("agenda_validated", "Ordre du jour validé"),
    ("decision_assigned", "Décision assignée"),
    ("decision_approved", "Décision validée"),
    ("decision_deadline", "Échéance décision"),
    ("decision_action_delay", "Décision en retard d'exécution"),
    ("task_assigned", "Tâche assignée"),
    ("task_delegated", "Tâche déléguée"),
    ("task_reminder", "Rappel tâche"),
    ("task_deadline", "Échéance tâche"),
    ("task_due_soon", "Échéance proche"),
    ("task_overdue", "Tâche en retard"),
    ("manager_daily_summary", "Résumé manager"),
    ("action_plan_blocked", "Plan d'action bloqué"),
    ("action_plan_completed", "Plan d'action clôturé"),
    ("plan_completed", "Plan d'action clôturé (legacy)"),
]

LEVEL_CHOICES = [
    ("info", "Information"), ("success", "Succès"),
    ("warning", "Avertissement"), ("danger", "Critique"),
]
PRIORITY_CHOICES = [
    ("low", "Faible"), ("normal", "Normale"),
    ("high", "Élevée"), ("critical", "Critique"),
]
CHANNEL_CHOICES = [
    ("internal", "Interne (in-app)"),
    ("email", "Email"),
    ("sms", "SMS"),
    ("whatsapp", "WhatsApp"),
    ("push", "Push"),
]
STATUS_CHOICES = [
    ("pending", "En attente"), ("sent", "Envoyée"),
    ("read", "Lue"), ("failed", "Échec"), ("skipped", "Ignorée"),
]
REMINDER_TYPE_CHOICES = [
    ("daily_user", "Rappel quotidien utilisateur"),
    ("manager_summary", "Résumé manager"),
    ("due_soon", "Échéance proche"),
    ("overdue", "Tâche en retard"),
]
SLOT_CHOICES = [
    ("morning", "Matin"),
    ("afternoon", "Après-midi"),
    ("anytime", "Quotidien"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("organizations", "0001_initial"),
        ("governance", "0001_initial"),
        ("action_plans", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ─── Notification : extension ─────────────────────────
        migrations.AlterField(
            model_name="notification",
            name="event",
            field=models.CharField(choices=EVENT_CHOICES, db_index=True, max_length=40),
        ),
        migrations.AddField(
            model_name="notification",
            name="subsidiary",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="organizations.subsidiary",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="direction",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="governance.direction",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="priority",
            field=models.CharField(choices=PRIORITY_CHOICES, db_index=True, default="normal", max_length=10),
        ),
        migrations.AddField(
            model_name="notification",
            name="channel",
            field=models.CharField(choices=CHANNEL_CHOICES, db_index=True, default="internal", max_length=10),
        ),
        migrations.AddField(
            model_name="notification",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, db_index=True, default="pending", max_length=10),
        ),
        migrations.AddField(
            model_name="notification",
            name="action_url",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="notification",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="failed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "channel", "status"], name="notif_recip_chan_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["subsidiary", "event"], name="notif_sub_event_idx"),
        ),

        # ─── NotificationPreference ───────────────────────────
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("internal_enabled", models.BooleanField(default=True)),
                ("sms_enabled", models.BooleanField(default=False)),
                ("whatsapp_enabled", models.BooleanField(default=False)),
                ("push_enabled", models.BooleanField(default=False)),
                ("task_assignment_email", models.BooleanField(default=True)),
                ("task_delegation_email", models.BooleanField(default=True)),
                ("daily_task_reminder", models.BooleanField(default=True)),
                ("manager_summary", models.BooleanField(default=True)),
                ("due_soon_alert", models.BooleanField(default=True)),
                ("overdue_alert", models.BooleanField(default=True)),
                ("decision_alerts", models.BooleanField(default=True)),
                ("meeting_alerts", models.BooleanField(default=True)),
                ("quiet_hours_start", models.TimeField(blank=True, null=True)),
                ("quiet_hours_end", models.TimeField(blank=True, null=True)),
                ("locale", models.CharField(default="fr-FR", max_length=8)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+",
                    to="organizations.organization",
                )),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_preference",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "indexes": [models.Index(fields=["user"], name="notif_pref_user_idx")],
            },
        ),

        # ─── NotificationLog ──────────────────────────────────
        migrations.CreateModel(
            name="NotificationLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(max_length=40)),
                ("channel", models.CharField(choices=CHANNEL_CHOICES, max_length=10)),
                ("status_code", models.CharField(blank=True, max_length=20)),
                ("response", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("notification", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="logs",
                    to="notifications.notification",
                )),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["notification", "-created_at"], name="notif_log_notif_idx"),
                    models.Index(fields=["channel", "status_code"], name="notif_log_chan_idx"),
                ],
            },
        ),

        # ─── TaskReminderLog ──────────────────────────────────
        migrations.CreateModel(
            name="TaskReminderLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reminder_type", models.CharField(choices=REMINDER_TYPE_CHOICES, max_length=20)),
                ("reminder_date", models.DateField(db_index=True)),
                ("time_slot", models.CharField(choices=SLOT_CHOICES, default="anytime", max_length=10)),
                ("channel", models.CharField(choices=CHANNEL_CHOICES, default="email", max_length=10)),
                ("status", models.CharField(choices=STATUS_CHOICES, default="sent", max_length=10)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("task", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reminder_logs",
                    to="action_plans.actiontask",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="task_reminder_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-reminder_date", "-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "task", "reminder_type", "reminder_date", "time_slot"),
                        name="uniq_reminder_per_user_task_slot",
                    ),
                ],
                "indexes": [
                    models.Index(fields=["user", "reminder_type", "reminder_date"], name="task_rem_user_idx"),
                ],
            },
        ),
    ]
