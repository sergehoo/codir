# Prompt — Module Meeting Recordings (Django Templates + JS vanilla)

Tu es un architecte senior Django. Ta mission : intégrer un module complet
d'enregistrement audio de réunions avec transcription IA, identification
manuelle des voix et génération automatique de compte rendu — dans une
plateforme Django classique (templates HTML, pas de SPA React/Vue).

Ce prompt est issu d'une implémentation production-ready déjà débuggée
(50+ correctifs documentés). Suis-le rigoureusement pour éviter les pièges.

---

## 1. STACK OBLIGATOIRE

### Backend
- Python 3.12, Django 5+ / 6
- PostgreSQL
- Celery 5.x + Redis (queue dédiée `recordings`)
- MinIO ou AWS S3 via `django-storages[s3]`
- AssemblyAI Python SDK (`assemblyai>=0.43`)
- Anthropic SDK (`anthropic>=0.51`)
- OpenAI SDK (`openai>=1.99`) — fallback DeepSeek
- `pydub` + `ffmpeg` (extraction extraits audio)
- `python-magic` (sniff MIME)

### Frontend (Django templates)
- Templates Django + Bootstrap 5 (ou Tailwind via CDN) — au choix
- **htmx** (recommandé) — pour le polling de statut sans framework JS
- **Alpine.js** (recommandé) — pour les modals et interactions locales
- JavaScript natif (modules ES) — pour MediaRecorder + audio player
- Pas de framework SPA. Pas de bundler obligatoire.

### Infrastructure
- Docker Compose
- Traefik HTTPS (ou Nginx)
- Volume MinIO persistant

---

## 2. ARCHITECTURE — VUE D'ENSEMBLE

```
┌──────────────────────────────────────────────────────────┐
│ FRONTEND (Django Templates + JS modules)                 │
│  - Page détail réunion : intégre <div id="recorder">     │
│  - JS module : capture micro (MediaRecorder API)         │
│  - htmx : polling de statut, mise à jour partielle       │
│  - Page identification voix : grille speakers + lecteurs │
│  - Page résumé : Markdown rendu + onglets               │
└──────────────────────────────────────────────────────────┘
                            │ HTTPS
                            ▼
┌──────────────────────────────────────────────────────────┐
│ BACKEND DJANGO                                           │
│  - Views classes-based (pages HTML)                      │
│  - Views API JSON pour les actions AJAX                  │
│  - Endpoints stream audio (token signé HMAC)             │
│  - Permissions via decorators                            │
└──────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌──────────┐  ┌────────────┐  ┌──────────────┐
       │ Postgres │  │ Celery     │  │ MinIO        │
       └──────────┘  │ (queue     │  │ (bucket :    │
                     │ recordings)│  │  recordings) │
                     └────────────┘  └──────────────┘
                            │
                            ▼ services backend
        ┌──────────┬──────────────┬──────────────┐
        │ AssemblyAI│  Anthropic  │  DeepSeek    │
        │ ASR + diarisation       │  fallback    │
        └──────────┴──────────────┴──────────────┘
```

---

## 3. PIPELINE COMPLET (10 étapes)

```
[1] Utilisateur ouvre /meetings/<id>/
    → Template inclut {% include "meeting_recordings/recorder_widget.html" %}
    → JS module recorder.js attaché au <div id="recorder">

[2] Click "Démarrer l'enregistrement"
    → Modal consentement (Alpine.js ou Bootstrap)
    → getUserMedia({ audio: true })
    → MediaRecorder en webm/opus
    → Timer + niveau audio visible

[3] Click "Arrêter"
    → Assemble le Blob
    → POST /meetings/<id>/recordings/upload/ (FormData multipart)
    → Réponse JSON : { recording_id, status: "uploaded" }
    → JS lance polling htmx vers /recordings/<rid>/status-fragment/

[4] Pipeline Celery (queue recordings)
    process_recording_task
      → transcribe_recording (AssemblyAI)
      → aggregate_speakers_from_segments
      → status = waiting_speaker_mapping
      → notify (email + in-app)

[5] Click sur la notification → redirige vers
    /meetings/<id>/recordings/<rid>/speakers/
    Template : grille des DetectedSpeaker
      - <audio src="/recordings/<rid>/speakers/<label>/sample/?token=..."> (avec token signé !)
      - <select> avec tous les MeetingParticipant
      - Bouton "Confirmer" (POST form)

[6] L'utilisateur écoute, sélectionne, soumet le formulaire
    → POST /recordings/<rid>/speaker-mapping/
    → Sauvegarde SpeakerParticipantMapping + maj DetectedSpeaker.mapped_participant
    → Si tous mappés : bouton "Confirmer et générer le CR"

[7] Click final
    → POST /recordings/<rid>/confirm-speakers/
    → Chaîne Celery : final_transcript → summarize → extract_decisions/actions
    → status = completed

[8] Notification finale → /recordings/<rid>/summary/
    Template avec onglets :
      - Résumé (Markdown rendu via django-markdownify ou markdown lib)
      - Décisions (cases à cocher)
      - Actions (cases à cocher)
      - Transcription complète

[9] L'utilisateur coche N décisions → POST /recordings/<rid>/create-decisions/
    → Crée objets Decision réels dans le module decisions/

[10] Idem actions → POST /recordings/<rid>/create-action-plans/
```

---

## 4. APP DJANGO — STRUCTURE

```
apps/meeting_recordings/
├── __init__.py
├── apps.py
├── admin.py
├── models.py
├── permissions.py
├── audio_tokens.py
├── forms.py                    # Django forms classiques
├── views.py                    # Class-based views (pages HTML)
├── api_views.py                # Vues JSON pour AJAX
├── urls.py
├── tasks.py                    # Celery tasks
├── signals.py
├── services/
│   ├── __init__.py
│   ├── recording.py
│   ├── audio_processing.py
│   ├── transcription.py
│   ├── diarization.py
│   ├── speaker_mapping.py
│   ├── ai_summary.py
│   └── extraction.py
├── templates/
│   └── meeting_recordings/
│       ├── recorder_widget.html         # à inclure dans meeting_detail
│       ├── speaker_mapping.html         # page complète
│       ├── recording_summary.html       # page complète
│       ├── status_fragment.html         # mise à jour htmx polling
│       └── components/
│           ├── speaker_card.html
│           ├── audio_player.html
│           └── consent_banner.html
├── static/
│   └── meeting_recordings/
│       ├── js/
│       │   ├── recorder.js              # MediaRecorder logic
│       │   ├── audio_player.js          # Lecteur waveform canvas
│       │   └── speaker_mapping.js       # Validation form
│       └── css/
│           └── recordings.css
├── migrations/
│   └── 0001_initial.py
└── tests/
    └── ...
```

---

## 5. MODÈLES DJANGO (`models.py`)

Identique au prompt React — section 4 du `PROMPT_MEETING_RECORDINGS.md`.
Tous les FileField utilisent `storage=_recordings_storage` pour cibler le
bucket `codir-recordings-prod` (séparé du bucket documents).

### Modèles à créer
1. **MeetingRecording** (entité racine + status + transcripts)
2. **RecordingChunk** (upload streamé optionnel)
3. **SpeakerSegment** (segments diarisés)
4. **DetectedSpeaker** (voix uniques avec sample_audio MP3)
5. **SpeakerParticipantMapping** (audit historique des mappings)
6. **RecordingAIExtraction** (brouillons IA à valider)

```python
# models.py — helper storage critique
from django.core.files.storage import storages

def _recordings_storage():
    """Force le bucket dédié recordings (séparé du default).
    ⚠️ Sans ça, audio et samples partent dans des buckets différents → 404."""
    try:
        return storages["recordings"]
    except Exception:
        return storages["default"]


class MeetingRecording(models.Model):
    meeting = models.ForeignKey("meetings.Meeting", on_delete=models.CASCADE,
                                 related_name="recordings")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name="recordings_made")
    audio_file = models.FileField(
        upload_to=_audio_upload_path, max_length=600, null=True, blank=True,
        storage=_recordings_storage,
    )
    # ... (cf. prompt React section 4.2 pour la liste complète)


class DetectedSpeaker(models.Model):
    recording = models.ForeignKey(MeetingRecording, on_delete=models.CASCADE,
                                   related_name="speakers")
    speaker_label = models.CharField(max_length=40, db_index=True)
    display_name = models.CharField(max_length=200, blank=True)
    sample_audio = models.FileField(
        upload_to=_speaker_sample_upload_path, max_length=600, null=True, blank=True,
        storage=_recordings_storage,  # ← critique
    )
    # ...
```

---

## 6. SERVICES BACKEND (`services/`)

Identique au prompt React — sections 5.1 à 5.7.

Points critiques :

### `transcription.py`
- Télécharger l'audio en **local /tmp** au lieu de passer URL publique à AssemblyAI
- **NE PAS passer `speech_model`** — laisser le défaut serveur (universal-2)
- Capter toutes les exceptions et stocker dans `recording.error_message`
- `finally:` cleanup du fichier temp

### `diarization.py`
- Fallback **SPEAKER_00** si AAI ne diarise pas (audio < 30s ou mono)
- try/except autour de `extract_speaker_sample` (continuer si 1 échoue)
- try/except autour de `ds.sample_audio.save()` (reset à None si upload S3 plante)

### `ai_summary.py`
- Fallback automatique **Anthropic Claude → DeepSeek**
- Coerce JSON tolérant (retire ```json``` éventuels)
- Prompts en français pour CODIR exécutif

---

## 7. CELERY TASKS

Identique au prompt React — section 7.

⚠️ Queue dédiée `recordings` dans `CELERY_TASK_ROUTES` :
```python
CELERY_TASK_ROUTES = {
    "apps.meeting_recordings.tasks.*": {"queue": "recordings"},
}
```

Worker doit écouter explicitement :
```bash
celery -A config worker -Q default,celery,notifications,recordings
```

---

## 8. URLS + VIEWS

### `urls.py`

```python
from django.urls import path
from . import views, api_views

app_name = "meeting_recordings"

urlpatterns = [
    # ─── PAGES HTML ─────────────────────────────────────────
    path("meetings/<uuid:meeting_id>/recordings/<uuid:rid>/speakers/",
         views.SpeakerMappingView.as_view(), name="speaker-mapping"),
    path("meetings/<uuid:meeting_id>/recordings/<uuid:rid>/summary/",
         views.RecordingSummaryView.as_view(), name="recording-summary"),

    # ─── FRAGMENTS HTML pour htmx polling ───────────────────
    path("recordings/<uuid:rid>/status-fragment/",
         views.RecordingStatusFragmentView.as_view(), name="status-fragment"),

    # ─── API JSON (utilisées par le JS module recorder.js) ──
    path("meetings/<uuid:meeting_id>/recordings/start/",
         api_views.start_recording, name="api-start"),
    path("meetings/<uuid:meeting_id>/recordings/upload/",
         api_views.upload_recording, name="api-upload"),
    path("recordings/<uuid:rid>/status/",
         api_views.recording_status, name="api-status"),

    # ─── FORMS POST (pages d'identification + résumé) ───────
    path("recordings/<uuid:rid>/speaker-mapping/",
         views.SpeakerMappingPostView.as_view(), name="post-mapping"),
    path("recordings/<uuid:rid>/confirm-speakers/",
         views.ConfirmSpeakersView.as_view(), name="confirm-speakers"),
    path("recordings/<uuid:rid>/create-decisions/",
         views.CreateDecisionsView.as_view(), name="create-decisions"),
    path("recordings/<uuid:rid>/create-action-plans/",
         views.CreateActionPlansView.as_view(), name="create-action-plans"),

    # ─── STREAM AUDIO (token signé pour <audio>) ───────────
    path("recordings/<uuid:rid>/audio/",
         api_views.stream_audio, name="stream-audio"),
    path("recordings/<uuid:rid>/speakers/<str:speaker_label>/sample/",
         api_views.stream_speaker_sample, name="stream-sample"),
]
```

### `views.py` — pages HTML

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.views.generic.base import View
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import MeetingRecording, DetectedSpeaker, RecordingStatus
from .services.speaker_mapping import (
    map_speaker_to_participant, confirm_all_mappings,
)


class SpeakerMappingView(LoginRequiredMixin, TemplateView):
    """Page d'identification des voix détectées."""
    template_name = "meeting_recordings/speaker_mapping.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rid = self.kwargs["rid"]
        meeting_id = self.kwargs["meeting_id"]
        # ⚠️ unscoped si auth via token (sinon manager tenant retourne none)
        recording = get_object_or_404(MeetingRecording.unscoped, id=rid)
        # Vérif tenant + permission au cas par cas
        # ...

        speakers = DetectedSpeaker.unscoped.filter(
            recording=recording,
        ).order_by("speaker_label")

        # Liste des participants pour le select
        participants = recording.meeting.participants.select_related("user").filter(
            user__isnull=False,
        )
        participants_list = [
            {
                "id": str(p.user.id),
                "full_name": p.user.get_full_name() or p.user.email,
                "email": p.user.email,
            } for p in participants
        ]

        ctx.update({
            "meeting": recording.meeting,
            "recording": recording,
            "speakers": speakers,
            "participants": participants_list,
            "all_mapped": all(sp.mapped_participant_id for sp in speakers),
        })
        return ctx


class SpeakerMappingPostView(LoginRequiredMixin, View):
    """POST du formulaire de mapping voix → participant."""
    def post(self, request, rid):
        recording = get_object_or_404(MeetingRecording.unscoped, id=rid)
        # Pour chaque speaker, récupère le participant choisi
        speakers = DetectedSpeaker.unscoped.filter(recording=recording)
        for sp in speakers:
            participant_id = request.POST.get(f"speaker_{sp.speaker_label}")
            if participant_id:
                from apps.accounts.models import User
                participant = User.objects.filter(id=participant_id).first()
                if participant:
                    map_speaker_to_participant(
                        recording=recording,
                        speaker_label=sp.speaker_label,
                        participant=participant,
                        confirmed_by=request.user,
                    )
        messages.success(request, "Associations enregistrées.")
        return HttpResponseRedirect(request.path)


class ConfirmSpeakersView(LoginRequiredMixin, View):
    """POST : confirme tous les mappings et déclenche le pipeline IA."""
    def post(self, request, rid):
        from .tasks import (
            generate_final_transcript_task, summarize_recording_task,
        )
        recording = get_object_or_404(MeetingRecording.unscoped, id=rid)
        try:
            confirm_all_mappings(recording=recording, confirmed_by=request.user)
        except ValueError as exc:
            messages.error(request, f"Impossible de confirmer : {exc}")
            return HttpResponseRedirect(
                f"/meetings/{recording.meeting_id}/recordings/{rid}/speakers/"
            )
        generate_final_transcript_task.delay(str(rid))
        summarize_recording_task.apply_async(args=[str(rid)], countdown=2)
        messages.info(request, "Génération du CR en cours…")
        return HttpResponseRedirect(
            f"/meetings/{recording.meeting_id}/recordings/{rid}/summary/"
        )


class RecordingStatusFragmentView(LoginRequiredMixin, TemplateView):
    """Fragment HTML pour htmx polling — affiche l'avancement du pipeline."""
    template_name = "meeting_recordings/status_fragment.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        recording = get_object_or_404(MeetingRecording.unscoped, id=self.kwargs["rid"])
        ctx["recording"] = recording
        ctx["is_terminal"] = recording.status in ("completed", "failed",
                                                    "waiting_speaker_mapping")
        return ctx
```

### `api_views.py` — endpoints JSON + stream

```python
import json
import logging
from django.http import JsonResponse, StreamingHttpResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt  # ou utiliser CSRF token
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import MeetingRecording, DetectedSpeaker, RecordingStatus
from .services.recording import create_recording, mark_uploaded, update_status
from .audio_tokens import generate_audio_token, verify_audio_token

logger = logging.getLogger(__name__)


@require_POST
@login_required
def upload_recording(request, meeting_id):
    """Upload du Blob audio depuis le JS recorder."""
    from apps.meetings.models import Meeting
    meeting = get_object_or_404(Meeting, id=meeting_id)

    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"detail": "Fichier audio requis."}, status=400)

    # Vérif taille
    from django.conf import settings
    max_mb = getattr(settings, "MAX_RECORDING_UPLOAD_MB", 600)
    if audio.size > max_mb * 1024 * 1024:
        return JsonResponse(
            {"detail": f"Fichier trop volumineux (max {max_mb} Mo)."},
            status=400,
        )

    consent_ack = request.POST.get("consent_acknowledged") == "true"
    duration = float(request.POST.get("duration_seconds", 0) or 0)

    rec_id = request.POST.get("recording_id")
    if rec_id:
        recording = get_object_or_404(MeetingRecording, id=rec_id, meeting=meeting)
    else:
        recording = create_recording(
            meeting=meeting, recorded_by=request.user,
            consent_acknowledged=consent_ack,
        )

    update_status(recording, RecordingStatus.UPLOADING)
    try:
        mark_uploaded(
            recording, file_obj=audio,
            mime_type=audio.content_type or "",
            original_filename=audio.name,
            duration_seconds=duration,
        )
    except Exception as exc:
        logger.exception("upload mark_uploaded KO")
        return JsonResponse(
            {"detail": f"Erreur stockage : {exc}", "recording_id": str(recording.id)},
            status=502,
        )

    from .tasks import process_recording_task
    process_recording_task.delay(str(recording.id))

    return JsonResponse({
        "recording_id": str(recording.id),
        "status": recording.status,
        "status_url": f"/recordings/{recording.id}/status/",
        "redirect_url": (
            f"/meetings/{meeting.id}/recordings/{recording.id}/speakers/"
        ),
    }, status=202)


@require_GET
@login_required
def recording_status(request, rid):
    """Polling JSON pour le frontend (ou htmx)."""
    rec = get_object_or_404(MeetingRecording.unscoped, id=rid)
    return JsonResponse({
        "id": str(rec.id),
        "status": rec.status,
        "duration_seconds": rec.duration_seconds,
        "speakers_count": DetectedSpeaker.unscoped.filter(recording=rec).count(),
        "error_message": rec.error_message,
        "redirect_url": (
            f"/meetings/{rec.meeting_id}/recordings/{rec.id}/speakers/"
            if rec.status == "waiting_speaker_mapping"
            else f"/meetings/{rec.meeting_id}/recordings/{rec.id}/summary/"
            if rec.status == "completed"
            else None
        ),
    })


@require_GET
def stream_audio(request, rid):
    """Stream l'audio complet — token signé en query string."""
    return _stream_audio_endpoint(request, rid)


@require_GET
def stream_speaker_sample(request, rid, speaker_label):
    """Stream un extrait audio d'un speaker — token signé."""
    # ⚠️ unscoped car pas de tenant context via token
    recording = MeetingRecording.unscoped.filter(id=rid).first()
    if recording is None:
        raise Http404("Recording introuvable.")

    # Vérif token signé (HMAC) OU Bearer session
    if not _verify_audio_access(request):
        return JsonResponse({"detail": "Token audio invalide."}, status=401)

    # ⚠️ unscoped ici aussi
    speaker = DetectedSpeaker.unscoped.filter(
        recording=recording, speaker_label=speaker_label,
    ).first()
    if speaker is None:
        raise Http404("Speaker inconnu.")
    if not speaker.sample_audio or not speaker.sample_audio.name:
        raise Http404("Extrait audio non généré.")

    return _stream_file_response(
        speaker.sample_audio,
        content_type="audio/mpeg",
        filename=f"{speaker_label}.mp3",
    )


def _verify_audio_access(request):
    """Vérifie l'auth : token signé OU session Django authentifiée."""
    token = request.GET.get("token")
    if token:
        payload = verify_audio_token(token=token, resource_path=request.path)
        return payload is not None
    return request.user.is_authenticated


def _stream_file_response(file_field, *, content_type, filename):
    """Stream un FileField au navigateur — bypass URL publique S3/MinIO."""
    try:
        file_field.open("rb")
    except Exception as exc:
        logger.exception("Impossible d'ouvrir audio : %s", exc)
        raise Http404("Fichier inaccessible.")

    def _iter():
        try:
            while True:
                chunk = file_field.read(64 * 1024)
                if not chunk: break
                yield chunk
        finally:
            try: file_field.close()
            except: pass

    response = StreamingHttpResponse(_iter(), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "private, max-age=3600"
    response["Accept-Ranges"] = "bytes"
    return response
```

---

## 9. TEMPLATES

### `meeting_recordings/recorder_widget.html`

Widget à inclure dans `meeting_detail.html` :

```html
{% load static %}

<section class="card mt-4">
  <div class="card-body" x-data="recorderWidget('{{ meeting.id }}', {{ existing_recording_id|default:'null' }})">
    <h5 class="card-title">
      <i class="bi bi-mic-fill text-primary"></i>
      Enregistrement & compte rendu IA
    </h5>

    <!-- Bannière consentement -->
    <div x-show="phase === 'idle'" class="alert alert-warning">
      <h6>⚠️ Consentement requis</h6>
      <p class="mb-2">
        Cette réunion sera enregistrée à des fins de compte rendu. Les participants
        doivent être informés avant le début.
      </p>
      <label class="form-check">
        <input type="checkbox" class="form-check-input" x-model="consentAck">
        J'ai informé les participants et j'assume la responsabilité.
      </label>
    </div>

    <!-- Bouton démarrer -->
    <button x-show="phase === 'idle'"
            class="btn btn-primary btn-lg"
            :disabled="!consentAck"
            @click="startRecording()">
      <i class="bi bi-record-circle"></i>
      Démarrer l'enregistrement
    </button>

    <!-- Contrôles pendant l'enregistrement -->
    <div x-show="phase === 'recording'" class="recording-controls">
      <div class="d-flex align-items-center gap-3">
        <div class="recording-indicator pulse"></div>
        <span class="fw-bold" x-text="formatDuration(durationMs)"></span>
        <div class="audio-level-bars" id="audioLevelBars"></div>
        <button class="btn btn-outline-secondary" @click="pauseRecording()" x-show="!isPaused">
          <i class="bi bi-pause-fill"></i> Pause
        </button>
        <button class="btn btn-warning" @click="resumeRecording()" x-show="isPaused">
          <i class="bi bi-play-fill"></i> Reprendre
        </button>
        <button class="btn btn-danger" @click="stopRecording()">
          <i class="bi bi-stop-fill"></i> Arrêter
        </button>
      </div>
    </div>

    <!-- Upload en cours -->
    <div x-show="phase === 'uploading'" class="upload-progress">
      <p>Envoi de l'audio…</p>
      <div class="progress">
        <div class="progress-bar" :style="`width: ${uploadProgress}%`"
             x-text="`${uploadProgress}%`"></div>
      </div>
    </div>

    <!-- Pipeline IA en cours — htmx polling -->
    <div x-show="phase === 'processing'"
         hx-get="/recordings/{{ recording.id }}/status-fragment/"
         hx-trigger="load, every 3s"
         hx-swap="innerHTML">
      <div class="spinner-border text-primary"></div>
      Traitement en cours…
    </div>

    <!-- Erreur -->
    <div x-show="error" class="alert alert-danger">
      <strong>Erreur :</strong>
      <span x-text="error"></span>
      <button x-show="savedBlob" class="btn btn-sm btn-warning mt-2"
              @click="retryUpload()">
        Réessayer l'envoi
      </button>
    </div>
  </div>
</section>

<script type="module" src="{% static 'meeting_recordings/js/recorder.js' %}"></script>
```

### `meeting_recordings/status_fragment.html`

Pour le polling htmx :

```html
{% load i18n %}

<div class="pipeline-status">
  {% if recording.status == "transcribing" %}
    <div class="alert alert-info">
      <i class="bi bi-mic"></i>
      Transcription AssemblyAI en cours…
    </div>
  {% elif recording.status == "diarizing" %}
    <div class="alert alert-info">
      <i class="bi bi-people"></i>
      Détection des voix…
    </div>
  {% elif recording.status == "waiting_speaker_mapping" %}
    <div class="alert alert-success">
      <strong>✓ Voix détectées !</strong>
      <a href="/meetings/{{ recording.meeting_id }}/recordings/{{ recording.id }}/speakers/"
         class="btn btn-primary btn-sm ms-2">
        Identifier les voix
      </a>
    </div>
  {% elif recording.status == "completed" %}
    <div class="alert alert-success">
      <strong>✓ Compte rendu prêt !</strong>
      <a href="/meetings/{{ recording.meeting_id }}/recordings/{{ recording.id }}/summary/"
         class="btn btn-success btn-sm ms-2">
        Voir le résumé
      </a>
    </div>
  {% elif recording.status == "failed" %}
    <div class="alert alert-danger">
      <strong>Échec :</strong>
      {{ recording.error_message|default:"Erreur inconnue" }}
    </div>
  {% else %}
    <div class="alert alert-secondary">
      <div class="spinner-border spinner-border-sm"></div>
      {{ recording.get_status_display }}
    </div>
  {% endif %}

  {% if is_terminal %}
  {# Arrête le polling htmx en ne déclenchant plus #}
  <script>document.dispatchEvent(new CustomEvent('recording-terminal'))</script>
  {% endif %}
</div>
```

### `meeting_recordings/speaker_mapping.html`

```html
{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="container py-4">
  <a href="{% url 'meetings:detail' meeting.id %}" class="btn btn-link">
    ← Retour à la réunion
  </a>

  <h1 class="h2 mt-3">
    <i class="bi bi-mic-fill"></i>
    Identifier les voix détectées
  </h1>
  <p class="text-muted">{{ meeting.title }}</p>

  <div class="alert alert-warning">
    <strong>Identification manuelle</strong> : le système détecte les voix
    distinctes mais ne reconnaît pas automatiquement qui parle. Écoutez chaque
    extrait et associez la voix à un participant.
  </div>

  <form method="post" action="{% url 'meeting_recordings:post-mapping' recording.id %}">
    {% csrf_token %}

    <div class="row g-3">
      {% for speaker in speakers %}
      <div class="col-md-6 col-lg-4">
        <div class="card h-100">
          <div class="card-body">
            <h5 class="card-title">
              <i class="bi bi-person-fill"></i>
              {{ speaker.speaker_label }}
              {% if speaker.is_confirmed %}
              <span class="badge bg-success">CONFIRMÉ</span>
              {% endif %}
            </h5>
            <p class="text-muted small">
              {{ speaker.total_duration|floatformat:0 }} sec · {{ speaker.total_segments }} segment{{ speaker.total_segments|pluralize }}
            </p>

            {% if speaker.sample_audio %}
            <audio controls class="w-100" preload="metadata">
              <source src="{% url 'meeting_recordings:stream-sample' recording.id speaker.speaker_label %}?token={{ speaker.sample_audio_token }}"
                      type="audio/mpeg">
            </audio>
            {% else %}
            <p class="text-muted small">Extrait audio non disponible</p>
            {% endif %}

            <label class="form-label mt-3">Associer à :</label>
            <select name="speaker_{{ speaker.speaker_label }}" class="form-select">
              <option value="">— Sélectionner —</option>
              {% for p in participants %}
              <option value="{{ p.id }}"
                {% if speaker.mapped_participant_id|stringformat:'s' == p.id %}selected{% endif %}>
                {{ p.full_name }}
              </option>
              {% endfor %}
            </select>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>

    <div class="mt-4 d-flex gap-2 justify-content-end">
      <button type="submit" class="btn btn-outline-primary">
        Enregistrer les associations
      </button>
      {% if all_mapped %}
      <button type="submit"
              formaction="{% url 'meeting_recordings:confirm-speakers' recording.id %}"
              class="btn btn-success">
        Confirmer et générer le CR →
      </button>
      {% endif %}
    </div>
  </form>
</div>
{% endblock %}
```

⚠️ **Important sur le token** : le serializer doit injecter le token signé.
Soit dans la vue Django (ajouté en context), soit comme property du modèle :

```python
# Dans la view ou un templatetag
from .audio_tokens import generate_audio_token

@property
def sample_audio_token(self):
    if not self.sample_audio: return ""
    return generate_audio_token(
        resource_path=f"/recordings/{self.recording_id}/speakers/{self.speaker_label}/sample/",
        user_id="anonymous",  # ou user actuel
        expiry_seconds=30*60,
    )
```

Ou plus propre — calculer le token au moment du rendu de template via custom template tag :

```python
# meeting_recordings/templatetags/recording_tags.py
from django import template
from ..audio_tokens import generate_audio_token

register = template.Library()

@register.simple_tag(takes_context=True)
def audio_token(context, path):
    user = context["request"].user
    return generate_audio_token(
        resource_path=path,
        user_id=str(user.id) if user.is_authenticated else "anon",
        expiry_seconds=30*60,
    )
```

Usage dans template :
```django
{% load recording_tags %}
{% audio_token "/recordings/123/speakers/SPEAKER_A/sample/" as tok %}
<audio src="{% url '...' %}?token={{ tok }}"></audio>
```

---

## 10. JAVASCRIPT — `recorder.js`

```javascript
// static/meeting_recordings/js/recorder.js
// Module ES — capture micro + upload via fetch + polling status

window.recorderWidget = function(meetingId, existingRecordingId = null) {
  return {
    // ─── State ────────────────────────────────────────────────
    phase: existingRecordingId ? 'processing' : 'idle',
    consentAck: false,
    durationMs: 0,
    audioLevel: 0,
    uploadProgress: 0,
    isPaused: false,
    error: null,
    recordingId: existingRecordingId,
    savedBlob: null,

    // ─── Internal MediaRecorder ──────────────────────────────
    _mediaRecorder: null,
    _stream: null,
    _chunks: [],
    _startMs: 0,
    _accumulatedMs: 0,
    _timerId: null,
    _audioCtx: null,
    _analyser: null,
    _rafId: null,

    // ─── Public API ──────────────────────────────────────────
    async startRecording() {
      this.error = null
      if (!this.consentAck) return

      try {
        this._stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        })
      } catch (err) {
        this.error = err.name === 'NotAllowedError'
          ? "Permission micro refusée. Activez-la dans les paramètres du navigateur."
          : `Impossible d'accéder au micro : ${err.message}`
        return
      }

      // MediaRecorder
      const mimeType = this._pickMimeType()
      this._mediaRecorder = new MediaRecorder(this._stream, mimeType ? { mimeType } : {})
      this._chunks = []
      this._mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) this._chunks.push(ev.data)
      }
      this._mediaRecorder.start(5000)

      // Timer
      this._startMs = Date.now()
      this._accumulatedMs = 0
      this._timerId = setInterval(() => {
        this.durationMs = Date.now() - this._startMs + this._accumulatedMs
      }, 200)

      // Audio level visualizer
      this._setupAudioLevel()

      this.phase = 'recording'
    },

    pauseRecording() {
      if (!this._mediaRecorder || this._mediaRecorder.state !== 'recording') return
      this._mediaRecorder.pause()
      this._accumulatedMs += Date.now() - this._startMs
      clearInterval(this._timerId)
      this.isPaused = true
    },

    resumeRecording() {
      if (!this._mediaRecorder || this._mediaRecorder.state !== 'paused') return
      this._mediaRecorder.resume()
      this._startMs = Date.now()
      this._timerId = setInterval(() => {
        this.durationMs = Date.now() - this._startMs + this._accumulatedMs
      }, 200)
      this.isPaused = false
    },

    async stopRecording() {
      const blob = await this._finalize()
      if (!blob) return
      this.savedBlob = blob
      await this._upload(blob)
    },

    async retryUpload() {
      if (!this.savedBlob) return
      await this._upload(this.savedBlob)
    },

    // ─── Helpers internes ────────────────────────────────────
    _pickMimeType() {
      const candidates = [
        'audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus',
      ]
      for (const c of candidates) {
        if (MediaRecorder.isTypeSupported(c)) return c
      }
      return ''
    },

    _setupAudioLevel() {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const src = ctx.createMediaStreamSource(this._stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      src.connect(analyser)
      this._audioCtx = ctx
      this._analyser = analyser
      const data = new Uint8Array(analyser.fftSize)
      const loop = () => {
        if (!this._analyser) return
        this._analyser.getByteTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128
          sum += v * v
        }
        this.audioLevel = Math.sqrt(sum / data.length)
        this._renderAudioBars()
        this._rafId = requestAnimationFrame(loop)
      }
      this._rafId = requestAnimationFrame(loop)
    },

    _renderAudioBars() {
      const el = document.getElementById('audioLevelBars')
      if (!el) return
      const bars = 12
      const lit = Math.min(bars, Math.round(this.audioLevel * bars * 3))
      let html = ''
      for (let i = 0; i < bars; i++) {
        const on = i < lit
        html += `<span class="audio-bar ${on ? 'active' : ''}"></span>`
      }
      el.innerHTML = html
    },

    _finalize() {
      return new Promise((resolve) => {
        if (!this._mediaRecorder) return resolve(null)
        this._mediaRecorder.onstop = () => {
          try {
            const blob = new Blob(this._chunks, { type: this._mediaRecorder.mimeType })
            this._cleanup()
            resolve(blob)
          } catch (err) {
            this._cleanup()
            resolve(null)
          }
        }
        try {
          this._mediaRecorder.stop()
        } catch {
          this._cleanup()
          resolve(null)
        }
      })
    },

    _cleanup() {
      try { this._stream?.getTracks().forEach((t) => t.stop()) } catch {}
      if (this._timerId) clearInterval(this._timerId)
      if (this._rafId) cancelAnimationFrame(this._rafId)
      try { this._audioCtx?.close() } catch {}
      this._mediaRecorder = null
      this._stream = null
    },

    async _upload(blob) {
      this.phase = 'uploading'
      this.uploadProgress = 0
      this.error = null

      const form = new FormData()
      if (this.recordingId) form.append('recording_id', this.recordingId)
      form.append('audio', new File([blob], 'recording.webm', { type: blob.type }))
      form.append('duration_seconds', String(this.durationMs / 1000))
      form.append('consent_acknowledged', String(this.consentAck))

      try {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', `/meetings/${meetingId}/recordings/upload/`)
        const csrftoken = this._getCookie('csrftoken')
        if (csrftoken) xhr.setRequestHeader('X-CSRFToken', csrftoken)
        xhr.upload.onprogress = (e) => {
          if (e.total) this.uploadProgress = Math.round(e.loaded / e.total * 100)
        }
        const res = await new Promise((resolve, reject) => {
          xhr.onload = () => resolve(xhr)
          xhr.onerror = () => reject(new Error('Erreur réseau'))
          xhr.send(form)
        })

        if (res.status >= 200 && res.status < 300) {
          const data = JSON.parse(res.responseText)
          this.recordingId = data.recording_id
          this.savedBlob = null
          this.phase = 'processing'
        } else {
          let detail
          try {
            detail = JSON.parse(res.responseText).detail
          } catch {
            detail = res.statusText
          }
          throw new Error(detail || `Erreur ${res.status}`)
        }
      } catch (err) {
        this.error = err.message
        this.phase = 'uploading' // reste sur l'erreur pour permettre retry
      }
    },

    _getCookie(name) {
      const match = document.cookie.match(`(^|;)\\s*${name}\\s*=\\s*([^;]+)`)
      return match ? match[2] : null
    },

    // Format mm:ss
    formatDuration(ms) {
      const s = Math.floor(ms / 1000)
      return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
    },
  }
}
```

---

## 11. SETTINGS DJANGO

Identique au prompt React — section 8.

Points-clés à ne PAS oublier :
- `STORAGES` à 2 buckets (`default` + `recordings`)
- `addressing_style=path` + `signature_version=s3v4` pour MinIO
- **PAS** de `ServerSideEncryption` sur MinIO standalone
- `MEDIA_ROOT="/var/www/media"` (volume writable)
- Celery routes : `recordings` queue
- Worker écoute `-Q default,celery,notifications,recordings`

---

## 12. PIÈGES CRITIQUES À ÉVITER (issus de 50+ debugs)

### 12.1 Permissions navigateur micro
`Permissions-Policy: microphone=()` bloque l'accès même avant `getUserMedia`.
Fix : header `microphone=(self)` côté Nginx/Traefik/Django middleware.

### 12.2 TenantManager + auth alternative
Quand l'auth se fait via **token signé** (sans login Django classique), les
managers tenant-aware retournent `.none()`.
Fix : utiliser `Model.unscoped.filter(...)` dans tous les endpoints stream.

### 12.3 Storage S3/MinIO
- `S3_SSE=AES256` incompatible MinIO standalone → ne pas l'activer.
- `addressing_style="path"` + `signature_version="s3v4"` obligatoires.
- 2 storages distincts : `default` (docs) + `recordings` (audio).
- Tous les `FileField` audio doivent utiliser `storage=_recordings_storage`.

### 12.4 Container Docker `read_only: true`
`MEDIA_ROOT` doit pointer vers un **volume monté** (`/var/www/media`), pas
vers `BASE_DIR/"media"` (qui est dans le rootfs read-only).

### 12.5 AssemblyAI
- Ne PAS spécifier `speech_model` (déprécié, défaut serveur recommandé).
- Ne PAS passer d'URL publique à AAI → télécharger audio en `/tmp` et passer le path local au SDK.
- Diarisation activée seulement si audio ≥ 30s + ≥ 2 voix → fallback `SPEAKER_00` sinon.

### 12.6 Audio HTML5
`<audio src>` n'envoie PAS de header `Authorization`.
Fix : token signé HMAC en query string `?token=...`.

### 12.7 Docker rebuild
`docker compose up --force-recreate` ne rebuild PAS l'image.
Toujours faire `docker compose build` d'abord après modif Python.

### 12.8 Heredoc dans docker exec
`docker compose exec` alloue un TTY par défaut → heredoc échoue.
Fix : ajouter `-T` (disable TTY).

### 12.9 Polling htmx
Pour arrêter le polling htmx quand le pipeline est terminé :
```html
<div hx-get="..." hx-trigger="load, every 3s"
     {% if is_terminal %}hx-trigger="none"{% endif %}>
```
Ou utiliser `hx-swap-oob` pour remplacer dynamiquement les attributs.

### 12.10 CSRF token en JS
Pour les uploads via `XMLHttpRequest` :
```js
xhr.setRequestHeader('X-CSRFToken', this._getCookie('csrftoken'))
```
Et s'assurer que la vue n'a PAS `@csrf_exempt` sauf si elle vérifie l'auth autrement.

### 12.11 MediaRecorder pause/resume
Le timer doit cumuler les durées entre pauses :
```js
pause:  accumulated += Date.now() - startMs
resume: startMs = Date.now()
total:  Date.now() - startMs + accumulated
```

### 12.12 ffmpeg dans le Dockerfile
Le worker Celery doit avoir ffmpeg installé pour pydub :
```dockerfile
RUN apt-get install -y ffmpeg libsndfile1
```

---

## 13. VARIABLES D'ENV

Identique au prompt React — section 13.

```env
# Storage
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=ChangeMe123!
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=${MINIO_ROOT_USER}
S3_SECRET_KEY=${MINIO_ROOT_PASSWORD}
S3_BUCKET=documents-prod
RECORDING_S3_BUCKET=recordings-prod
S3_REGION=eu-west-1
# Si tu utilises Traefik pour exposer MinIO :
S3_PUBLIC_DOMAIN=storage.example.com
S3_URL_PROTOCOL=https:

# Backup
MEDIA_ROOT=/var/www/media

# IA
ASSEMBLYAI_API_KEY=xxx
ASSEMBLYAI_LANGUAGE=fr

RECORDING_AI_PRIMARY=anthropic
RECORDING_AI_FALLBACK=deepseek
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Misc
MAX_RECORDING_UPLOAD_MB=600
SPEAKER_SAMPLE_DURATION_SEC=8
```

---

## 14. CHECKLIST D'INTÉGRATION

### Backend
- [ ] App `meeting_recordings` ajoutée à `INSTALLED_APPS`
- [ ] URLs incluses dans le `urls.py` principal
- [ ] Migrations appliquées
- [ ] Celery worker écoute la queue `recordings`
- [ ] Variables d'env définies (AssemblyAI, Anthropic, MinIO)
- [ ] ffmpeg installé dans le container
- [ ] Buckets MinIO créés au boot

### Frontend
- [ ] `{% include "meeting_recordings/recorder_widget.html" %}` dans la page meeting_detail
- [ ] htmx + Alpine.js chargés dans `base.html`
- [ ] Static `recorder.js` collecté (`collectstatic`)
- [ ] Custom template tag `audio_token` enregistré
- [ ] CSRF middleware actif

### Permissions
- [ ] Header `Permissions-Policy: microphone=(self)` côté reverse proxy
- [ ] HTTPS obligatoire (sinon getUserMedia bloqué)
- [ ] Endpoint stream audio bypass CSRF (token signé suffit)

### Tests E2E
- [ ] Démarrer un enregistrement depuis le détail réunion
- [ ] Voir le pipeline avancer (htmx polling)
- [ ] Identifier les voix sur la page mapping
- [ ] Confirmer et générer le CR
- [ ] Valider décisions/actions

---

## 15. INTÉGRATION DANS UNE PAGE EXISTANTE

Pour ajouter le module dans une page `meeting_detail.html` existante :

```html
{# meeting_detail.html — section à ajouter #}

<section class="meeting-section mt-5">
  <h3 class="section-title">Enregistrement & compte rendu IA</h3>

  {% with meeting.recordings.first as latest_recording %}
    {% include "meeting_recordings/recorder_widget.html" with meeting=meeting recording=latest_recording %}
  {% endwith %}
</section>

{# En bas du template, charger les dépendances JS #}
{% block extra_js %}
{{ block.super }}
<script src="https://unpkg.com/[email protected]" defer></script>
<script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
{% endblock %}
```

---

## 16. FIN DU PROMPT

Implémente en suivant rigoureusement les sections 4 à 10. Si tu rencontres des
ambiguïtés (modèle User, structure des permissions, framework CSS existant),
pose les questions AVANT de coder.

Priorités d'implémentation :
1. Modèles + migration
2. Services backend (`transcription.py` + `diarization.py` + `ai_summary.py`)
3. Celery tasks
4. URLs + views + api_views
5. Templates HTML
6. `recorder.js` JS module
7. Tests + déploiement

Le module est validé quand tu peux :
- Enregistrer une réunion de 1 min avec 2 voix distinctes
- Voir le pipeline passer en automatique jusqu'à `waiting_speaker_mapping`
- Écouter les 2 extraits audio sur la page mapping (token signé OK)
- Mapper les voix → confirmer → résumé IA généré
- Cocher 1 décision et 1 action → objets créés en DB
