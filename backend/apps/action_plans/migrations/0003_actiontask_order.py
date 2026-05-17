# Numéro d'ordre intra-plan pour ActionTask. Back-fill : ordre par due_date
# puis created_at au sein de chaque action_plan.
from django.db import migrations, models


def backfill_order(apps, schema_editor):
    """Attribue un numéro d'ordre séquentiel (1..N) aux tâches existantes
    de chaque plan, triées par (due_date NULLS LAST, created_at).
    """
    ActionTask = apps.get_model("action_plans", "ActionTask")
    ActionPlan = apps.get_model("action_plans", "ActionPlan")

    for plan in ActionPlan.objects.all():
        # Tri par due_date (nulls last) puis created_at.
        tasks = list(
            plan.tasks.all().order_by(
                models.F("due_date").asc(nulls_last=True),
                "created_at",
            )
        )
        for idx, task in enumerate(tasks, start=1):
            if task.order != idx:
                task.order = idx
                task.save(update_fields=["order"])


def reverse_noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("action_plans", "0002_co_assignees"),
    ]

    operations = [
        migrations.AddField(
            model_name="actiontask",
            name="order",
            field=models.PositiveIntegerField(
                default=0, db_index=True,
                help_text="Numéro d'ordre intra-plan d'action. 0 = non assigné (auto à la création).",
            ),
        ),
        migrations.AddIndex(
            model_name="actiontask",
            index=models.Index(fields=["action_plan", "order"], name="action_plan_order_idx"),
        ),
        migrations.AlterModelOptions(
            name="actiontask",
            options={"ordering": ["action_plan", "order", "due_date", "created_at"]},
        ),
        migrations.RunPython(backfill_order, reverse_noop),
    ]
