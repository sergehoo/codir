"""Ajout du champ subsidiary sur Decision (rattachement filiale)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("decisions", "0001_initial"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="decision",
            name="subsidiary",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="decisions",
                to="organizations.subsidiary",
                help_text="Filiale concernée par la décision (optionnel, cas Groupe si vide).",
            ),
        ),
    ]
