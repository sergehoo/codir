# MeetingSeries — template récurrent pour générer les instances de CODIR

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetings', '0002_smart_notes'),
        ('accounts', '0003_membership_subsidiary'),
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MeetingSeries',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('frequency', models.CharField(
                    choices=[
                        ('weekly', 'Hebdomadaire'),
                        ('biweekly', 'Bi-mensuel (toutes les 2 semaines)'),
                        ('monthly', 'Mensuel'),
                    ],
                    default='weekly',
                    max_length=20,
                )),
                ('day_of_week', models.PositiveSmallIntegerField(
                    choices=[
                        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
                        (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
                    ],
                    default=0,
                    help_text='Jour de la semaine pour weekly/biweekly. Pour monthly = jour du mois (1-28).',
                )),
                ('day_of_month', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    help_text='Pour frequency=monthly : jour du mois (1-28). Sinon ignoré.',
                )),
                ('time', models.TimeField(default='10:00', help_text='Heure locale de début')),
                ('duration_minutes', models.PositiveIntegerField(default=180)),
                ('meeting_type', models.CharField(
                    choices=[
                        ('regular', 'Ordinaire'), ('extraordinary', 'Extraordinaire'),
                        ('strategic', 'Stratégique'), ('crisis', 'De crise'),
                    ],
                    default='strategic',
                    max_length=20,
                )),
                ('location', models.CharField(blank=True, max_length=200)),
                ('video_url', models.URLField(blank=True)),
                ('generate_weeks_ahead', models.PositiveIntegerField(default=12, help_text="Nombre de semaines d'avance à générer (par défaut 12 = 3 mois).")),
                ('last_generated_until', models.DateField(blank=True, null=True, help_text='Date jusqu’à laquelle les instances ont été générées.')),
                ('is_active', models.BooleanField(default=True)),
                ('starts_on', models.DateField(blank=True, null=True, help_text='Date à partir de laquelle la série démarre (default : aujourd’hui).')),
                ('ends_on', models.DateField(blank=True, null=True, help_text='Date de fin éventuelle de la série (null = pas de fin).')),
                ('organization', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+',
                    to='organizations.organization',
                )),
                ('default_chair', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='meeting_series_as_chair',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('default_secretary', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='meeting_series_as_secretary',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('default_participants', models.ManyToManyField(
                    blank=True, related_name='meeting_series_default',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Série de réunions',
                'verbose_name_plural': 'Séries de réunions',
                'ordering': ['title'],
                'indexes': [
                    models.Index(fields=['organization', 'is_active'], name='meetings_se_org_act_idx'),
                ],
            },
        ),
        # FK Meeting.series + flag overrides_series
        migrations.AddField(
            model_name='meeting',
            name='series',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='instances',
                to='meetings.meetingseries',
                help_text='Série récurrente qui a généré cette instance. Null = réunion ponctuelle.',
            ),
        ),
        migrations.AddField(
            model_name='meeting',
            name='overrides_series',
            field=models.BooleanField(
                default=False,
                help_text='True si cette instance a été modifiée et diverge du template.',
            ),
        ),
        migrations.AddIndex(
            model_name='meeting',
            index=models.Index(fields=['series', 'scheduled_start'], name='meetings_me_series_dt_idx'),
        ),
    ]
