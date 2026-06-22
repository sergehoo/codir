"""Rename auto d'index suite à un changement de Meta sur ActionTask.

Django génère un nom déterministe par hash quand on ne le fournit pas
explicitement. L'ancien nom `action_plan_order_idx` (legacy ou collision)
doit être remplacé par le nouveau nom hashé `action_plan_action__fd9418_idx`.

Cette migration est triviale (RenameIndex côté SQL) et n'affecte aucune donnée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("action_plans", "0004_plan_decision_to_fk"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="actiontask",
            new_name="action_plan_action__fd9418_idx",
            old_name="action_plan_order_idx",
        ),
    ]
