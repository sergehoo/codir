# Migration : ajout du flag skip_speaker_detection sur MeetingRecording.
#
# Permet à l'utilisateur de demander un traitement accéléré qui saute la
# diarisation (détection des voix) ET l'étape d'identification utilisateur.
# Le pipeline enchaîne directement transcription → résumé IA, sans attribution
# par speaker. Gain : facteur ~2-3× sur le temps total (surtout pour audios
# mono-locuteur ou quand l'identification par voix n'est pas critique).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meeting_recordings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingrecording",
            name="skip_speaker_detection",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si True : on saute la diarisation (détection des voix) et "
                    "l'étape d'identification utilisateur. Le résumé IA est "
                    "généré directement depuis le texte brut, sans attribution "
                    "par speaker. Utile pour les audios mono-locuteur ou quand "
                    "on veut accélérer le pipeline (×2-3 plus rapide)."
                ),
            ),
        ),
    ]
