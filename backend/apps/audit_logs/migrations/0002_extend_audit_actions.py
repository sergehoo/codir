# Migration : étend les choices de AuditLog.action pour couvrir les
# évènements de connexion (login_failed) et de gestion des utilisateurs
# (password_reset, user_created, user_deactivated, user_reactivated, user_reassigned).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit_logs", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "Créé"),
                    ("updated", "Mis à jour"),
                    ("deleted", "Supprimé"),
                    ("validated", "Validé"),
                    ("approved", "Approuvé"),
                    ("closed", "Clôturé"),
                    ("started", "Démarré"),
                    ("completed", "Terminé"),
                    ("cancelled", "Annulé"),
                    ("login", "Connexion"),
                    ("logout", "Déconnexion"),
                    ("login_failed", "Échec de connexion"),
                    ("password_reset", "Réinitialisation mot de passe"),
                    ("user_created", "Compte utilisateur créé"),
                    ("user_deactivated", "Compte désactivé"),
                    ("user_reactivated", "Compte réactivé"),
                    ("user_reassigned", "Affectation mise à jour"),
                    ("custom", "Custom"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
