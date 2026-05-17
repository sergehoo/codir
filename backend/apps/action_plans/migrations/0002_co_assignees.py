# Co-responsables sur les tâches : permet d'affecter une tâche à plusieurs personnes

from django.conf import settings
from django.db import migrations, models


def copy_assignee_to_co_assignees(apps, schema_editor):
    """Pour les tâches existantes ayant un assignee, on l'ajoute aussi
    dans co_assignees pour que la liste 'tous les responsables' inclue le lead.
    NB : c'est facultatif — le lead reste accessible via task.assignee.
    On ne fait PAS cette copie pour garder une distinction claire :
        assignee = lead, co_assignees = équipiers additionnels.
    """
    # Volontairement vide : le lead reste séparé des co-assignees.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('action_plans', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='actiontask',
            name='co_assignees',
            field=models.ManyToManyField(
                blank=True,
                help_text="Co-responsables (équipiers). Le 'assignee' principal reste le lead.",
                related_name='tasks_co_assigned',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='actiontask',
            name='assignee',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Responsable principal (lead). Pour les co-responsables, utiliser co_assignees.",
                on_delete=models.deletion.SET_NULL,
                related_name='tasks_assigned',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(copy_assignee_to_co_assignees, reverse_code=migrations.RunPython.noop),
    ]
