"""Lot 2 — Agent IA proactif : pref par utilisateur pour activer/désactiver."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_weekly_user_digest"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="proactive_agent_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "L'agent IA proactif scrute les health_scores et envoie "
                    "des messages d'alerte dans le sidebar chat. Désactivable "
                    "pour stopper toute initiation IA non sollicitée."
                ),
            ),
        ),
    ]
