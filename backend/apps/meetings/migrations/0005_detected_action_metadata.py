# Champs date / priorité / description extraits par le parser de notes
# intelligent et propagés à la matérialisation des ActionTask.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0004_sync_state_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingdetectedaction",
            name="description_md",
            field=models.TextField(
                blank=True,
                help_text="Description extraite des lignes indentées sous la tâche.",
            ),
        ),
        migrations.AddField(
            model_name="meetingdetectedaction",
            name="due_date",
            field=models.DateField(
                null=True, blank=True,
                help_text="Échéance extraite d'un pattern DD/MM/YYYY dans la ligne.",
            ),
        ),
        migrations.AddField(
            model_name="meetingdetectedaction",
            name="priority",
            field=models.CharField(
                max_length=10, blank=True,
                help_text="Priorité extraite d'un !low|!medium|!high|!critical inline.",
            ),
        ),
    ]
