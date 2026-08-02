# Migration lot HIST : historisation des comptes rendus IA.
#
# 1. RecordingMinutesVersion — snapshot immuable du CR à chaque écrasement
#    (régénération IA ou édition manuelle), permettant consultation de
#    l'historique et restauration d'une version antérieure.
# 2. Champs d'archivage/annotation sur MeetingRecording — permet d'écarter
#    les takes ratés (uploads en échec) sans les détruire, et de leur donner
#    un titre parlant + une note interne.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "meeting_recordings",
            "0004_rename_mr_dspk_rec_conf_idx_meeting_rec_recordi_be7e94_idx_and_more",
        ),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Archivage / annotation sur MeetingRecording ──
        migrations.AddField(
            model_name="meetingrecording",
            name="is_archived",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text=(
                    "Si True : l'enregistrement est masqué de la vue principale sans "
                    "être détruit. Sert à écarter les takes ratés (uploads échoués) "
                    "tout en conservant la traçabilité."
                ),
            ),
        ),
        migrations.AddField(
            model_name="meetingrecording",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meetingrecording",
            name="internal_note",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Note libre interne sur cet enregistrement "
                    "(contexte, qualité audio…)."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="meetingrecording",
            index=models.Index(
                fields=["organization", "meeting", "is_archived"],
                name="meeting_rec_organiz_a1f3d2_idx",
            ),
        ),
        # ── RecordingMinutesVersion ──
        migrations.CreateModel(
            name="RecordingMinutesVersion",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version_number", models.PositiveIntegerField(
                    help_text="Incrément par recording, commence à 1.",
                )),
                ("summary", models.TextField(
                    blank=True, help_text="Résumé exécutif à cet instant.",
                )),
                ("ai_minutes", models.TextField(
                    blank=True, help_text="CR complet Markdown à cet instant.",
                )),
                ("origin", models.CharField(
                    choices=[
                        ("ai_generated", "Génération IA"),
                        ("ai_regenerated", "Régénération IA"),
                        ("manual_edit", "Édition manuelle"),
                        ("restored", "Restauration d'une version"),
                    ],
                    db_index=True,
                    default="ai_generated",
                    max_length=20,
                )),
                ("label", models.CharField(
                    blank=True,
                    help_text="Libellé optionnel (ex. « Avant correction chiffres »).",
                    max_length=200,
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="minutes_versions_created",
                    to=settings.AUTH_USER_MODEL,
                    help_text=(
                        "Auteur de l'action ayant produit cette version "
                        "(null si automate)."
                    ),
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="+", to="organizations.organization",
                )),
                ("recording", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="minutes_versions",
                    to="meeting_recordings.meetingrecording",
                )),
                ("restored_from", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="restorations",
                    to="meeting_recordings.recordingminutesversion",
                )),
            ],
            options={
                "ordering": ["-version_number"],
            },
        ),
        migrations.AddIndex(
            model_name="recordingminutesversion",
            index=models.Index(
                fields=["recording", "-version_number"],
                name="mr_minutes_ver_rec_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="recordingminutesversion",
            index=models.Index(
                fields=["organization", "-created_at"],
                name="mr_minutes_ver_org_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="recordingminutesversion",
            constraint=models.UniqueConstraint(
                fields=("recording", "version_number"),
                name="uniq_minutes_version_per_recording",
            ),
        ),
    ]
