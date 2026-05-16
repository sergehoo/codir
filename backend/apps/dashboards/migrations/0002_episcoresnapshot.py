# Generated for EPI Score v2 — daily snapshot model

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        ('dashboards', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EpiScoreSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(db_index=True)),
                ('overall_score', models.PositiveSmallIntegerField(help_text='EPI final 0-100')),
                ('completion_score', models.PositiveSmallIntegerField(default=0)),
                ('punctuality_score', models.PositiveSmallIntegerField(default=0)),
                ('velocity_score', models.PositiveSmallIntegerField(default=0)),
                ('quorum_score', models.PositiveSmallIntegerField(default=0)),
                ('overdue_penalty', models.PositiveSmallIntegerField(default=0, help_text='Points retirés (0-30)')),
                ('tasks_total', models.PositiveIntegerField(default=0)),
                ('tasks_done', models.PositiveIntegerField(default=0)),
                ('tasks_done_on_time', models.PositiveIntegerField(default=0)),
                ('tasks_overdue', models.PositiveIntegerField(default=0)),
                ('avg_days_to_close', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('meetings_total', models.PositiveIntegerField(default=0)),
                ('meetings_quorum_reached', models.PositiveIntegerField(default=0)),
                ('drop_alert_sent', models.BooleanField(default=False, help_text='True si alerte chute envoyée')),
                ('drop_vs_previous', models.SmallIntegerField(default=0, help_text='Delta vs jour J-1 (peut être négatif)')),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='epi_snapshots',
                    to='organizations.organization',
                )),
            ],
            options={
                'ordering': ['-date'],
                'unique_together': {('organization', 'date')},
                'indexes': [
                    models.Index(fields=['organization', '-date'], name='dashboards__org_dat_idx'),
                ],
            },
        ),
    ]
