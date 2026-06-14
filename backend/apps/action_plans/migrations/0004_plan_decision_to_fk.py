# Migration : ActionPlan.decision OneToOneField → ForeignKey nullable.
#
# But : autoriser plusieurs plans par décision (court terme + moyen terme)
# ET autoriser des plans standalone sans décision parente.
#
# Compatibilité : les données existantes (1 plan max par décision) restent
# valides — un ForeignKey n'impose pas d'unicité contrairement à OneToOne.
# Le related_name passe de `action_plan` (singulier) à `action_plans`
# (pluriel) pour cohérence avec la cardinalité réelle.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("action_plans", "0003_actiontask_order"),
        ("decisions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="actionplan",
            name="decision",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="action_plans",
                to="decisions.decision",
            ),
        ),
    ]
