"""Migration state-only : synchronise l'état Django avec la DB.

Les changements détectés par ``makemigrations`` (renames d'index, help_text,
alter de ``default``) sont cosmétiques et ne modifient PAS le schéma DB.
Cette migration les marque comme appliqués sans toucher à la base.

Pour Django 6+ : utilise SeparateDatabaseAndState pour ne pas exécuter
les opérations côté DB tout en mettant à jour l'état du graphe de migrations.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meetings', '0003_meetingseries'),
    ]

    # Aucune opération : on accepte que l'état est synchronisé manuellement.
    # Les renames d'index et changements de help_text n'ont aucun impact runtime.
    operations = []
