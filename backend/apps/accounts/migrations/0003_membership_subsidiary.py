# Membership.subsidiary — relation directe Employé ↔ Filiale

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='subsidiary',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='memberships',
                to='organizations.subsidiary',
                help_text='Filiale principale du collaborateur (peut être null pour les rôles transverses Groupe).',
            ),
        ),
        # Note : l'index (organization, subsidiary, is_active) est déclaré dans
        # Meta.indexes du modèle. Django le créera via makemigrations standard
        # plutôt qu'ici, évitant les conflits de nom sur les déploiements
        # incrémentaux.
    ]
