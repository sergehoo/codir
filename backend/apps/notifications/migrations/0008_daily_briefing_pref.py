"""Lot Briefing-Auto : préférences d'envoi quotidien (push + email)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_pushsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="daily_briefing_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="notificationpreference",
            name="daily_briefing_hour",
            field=models.PositiveSmallIntegerField(
                default=7,
                help_text="Heure locale (0-23) d'envoi du briefing matinal.",
            ),
        ),
    ]
