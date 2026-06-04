# Migration : ajout de WEEKLY_USER_DIGEST sur les enums
# (Notification.event + TaskReminderLog.reminder_type)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_user_events"),
    ]

    operations = [
        # ── Notification.event : ajout du choix WEEKLY_USER_DIGEST ──
        migrations.AlterField(
            model_name="notification",
            name="event",
            field=models.CharField(
                choices=[
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
                    ("user_created", "Bienvenue — compte créé"),
                    ("user_password_reset", "Mot de passe réinitialisé"),
                    ("user_reassigned", "Affectation mise à jour"),
                    ("user_deactivated", "Compte désactivé"),
                    ("user_reactivated", "Compte réactivé"),
                    ("weekly_user_digest", "Synthèse hebdomadaire des tâches"),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
        # ── TaskReminderLog.reminder_type : ajout WEEKLY_USER_DIGEST ──
        migrations.AlterField(
            model_name="taskreminderlog",
            name="reminder_type",
            field=models.CharField(
                choices=[
                    ("daily_user", "Rappel quotidien utilisateur"),
                    ("weekly_user_digest", "Synthèse hebdomadaire utilisateur"),
                    ("manager_summary", "Résumé manager"),
                    ("due_soon", "Échéance proche"),
                    ("overdue", "Tâche en retard"),
                ],
                max_length=20,
            ),
        ),
    ]
