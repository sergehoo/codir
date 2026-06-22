"""Multi-org branding — ajoute surface_color (ton de fond) sur Organization.

Cette 3e couleur (en plus de primary_color et secondary_color) contrôle
la teinte des fonds : page, sidebar, surfaces élevées. Le frontend dérive
automatiquement une rampe d'élévation (bg-subtle, bg-elevated) à partir
de cette valeur.

Default `#131210` = encre profonde Kaydan (préserve l'apparence actuelle).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        # ⚠️ On en profite pour aligner les help_text des couleurs existantes,
        # ce qui produit aussi des AlterField — sans impact data.
        migrations.AlterField(
            model_name="organization",
            name="primary_color",
            field=models.CharField(
                default="#2563eb",
                help_text="Accent — boutons, liens, focus, chips. Format #RRGGBB.",
                max_length=7,
            ),
        ),
        migrations.AlterField(
            model_name="organization",
            name="secondary_color",
            field=models.CharField(
                default="#0ea5e9",
                help_text="Accent secondaire — headers emails sombres. Format #RRGGBB.",
                max_length=7,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="surface_color",
            field=models.CharField(
                default="#131210",
                help_text=(
                    "Ton de fond — base de la page, sidebar et surfaces. "
                    "Une rampe d'élévation (subtle/elevated) en est dérivée "
                    "automatiquement. Format #RRGGBB."
                ),
                max_length=7,
            ),
        ),
    ]
