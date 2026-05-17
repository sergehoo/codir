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
        migrations.AddIndex(
            model_name='membership',
            index=models.Index(
                fields=['organization', 'subsidiary', 'is_active'],
                name='accounts_me_org_sub_idx',
            ),
        ),
    ]
