"""Ajout de subsidiary + direction sur ActionPlan (rattachement organisationnel).

Cohérent avec Decision qui a désormais aussi ces deux champs. Permet aux
users de créer un dossier directement rattaché à une filiale/direction depuis
les formulaires (sans avoir à passer par une décision intermédiaire).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("action_plans", "0005_rename_action_plan_order_idx"),
        ("organizations", "0001_initial"),
        ("governance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionplan",
            name="subsidiary",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="action_plans",
                to="organizations.subsidiary",
                help_text="Filiale porteuse du dossier (vide = Groupe).",
            ),
        ),
        migrations.AddField(
            model_name="actionplan",
            name="direction",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="action_plans",
                to="governance.direction",
                help_text="Direction porteuse du dossier (optionnel).",
            ),
        ),
    ]
