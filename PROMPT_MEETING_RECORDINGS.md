# Prompt — Intégration du module Meeting Recordings (Audio + IA)

Tu es un architecte senior Django/DRF + React/TypeScript. Ta mission : intégrer un
module complet d'enregistrement audio de réunions avec transcription, diarisation
des voix, identification manuelle des participants, et génération automatique de
compte rendu IA (résumé + décisions + actions à valider).

Ce prompt est issu d'une **implémentation production-ready** déjà débuggée (45+
correctifs documentés). Suis-le rigoureusement pour éviter de re-rencontrer les
mêmes pièges.

---

## 1. STACK OBLIGATOIRE

### Backend
- Python 3.12, Django 5+ / 6, Django REST Framework
- PostgreSQL (modèles multi-tenant via manager scope)
- Celery 5.x + Redis (queue dédiée `recordings`)
- MinIO ou S3 via `django-storages[s3]`
- AssemblyAI Python SDK (`assemblyai>=0.43`)
- Anthropic SDK (`anthropic>=0.51`) — résumé IA primaire
- OpenAI SDK (`openai>=1.99`) — fallback DeepSeek (compat OpenAI API)
- `pydub` + `ffmpeg` (extraction extraits audio speakers)
- `python-magic` (sniff MIME upload)

### Frontend
- React 18+, TypeScript 5+
- TanStack Query v5, TanStack Router
- TailwindCSS, lucide-react, sonner (toasts)
- Audio Web API (capture micro, AudioContext, MediaRecorder)
- Aucune lib externe pour le drag-drop (HTML5 natif)

### Infrastructure
- Docker Compose (services : web, asgi, worker, beat, db, redis, minio, minio_init)
- Traefik en reverse-proxy (HTTPS via Let's Encrypt)
- Volume Docker pour MinIO `codir_minio_data`
- Bucket dédié recordings (séparé du bucket documents généraux)

---

## 2. ARCHITECTURE — VUE D'ENSEMBLE

```
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (React/Vite)                                       │
│  - MeetingRecorderButton (capture micro via MediaRecorder)  │
│  - RecordingControlPanel (waveform animé, pause/stop)       │
│  - SpeakerIdentificationPanel (mapping voix → participant)  │
│  - SmartAudioPlayer (lecture extraits avec waveform canvas) │
│  - RecordingSummaryPage (résumé IA + décisions + actions)   │
└─────────────────────────────────────────────────────────────┘
                            │ HTTPS via Traefik
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ BACKEND DJANGO/DRF                                          │
│  - Endpoints REST 17 actions (upload, status, speakers...)  │
│  - JWT auth + token signé pour <audio> tags                 │
│  - Stream proxy depuis MinIO interne (pas d'URL publique)   │
│  - Permissions tenant-aware                                 │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌──────────┐  ┌────────────┐  ┌──────────────┐
       │ Postgres │  │ Celery     │  │ MinIO        │
       │ (modèles)│  │ Workers    │  │ (storage)    │
       └──────────┘  │ - queue    │  │ - bucket :   │
                     │  recordings│  │   recordings │
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
[1] Utilisateur clique "Démarrer l'enregistrement" sur la page réunion
    → Bannière consentement (obligatoire)
    → getUserMedia({ audio: true }) avec contraintes (echoCancellation, noiseSuppression)
    → MediaRecorder en webm/opus

[2] User parle → Visualisation niveau audio + timer XXL

[3] User clique "Arrêter"
    → Blob audio assemblé
    → Upload multipart vers POST /meetings/{id}/recordings/upload/
    → status = uploading → uploaded
    → process_recording_task.delay() dispatché vers Celery queue 'recordings'

[4] Worker Celery : process_recording_task
    a. transcribe_recording_task → AssemblyAI
       - Télécharge l'audio en local (/tmp) — NE PAS passer d'URL publique
       - Appel SDK assemblyai avec speaker_labels=True
       - PAS de speech_model paramètre (déprécié, laisser défaut serveur)
       - Persiste SpeakerSegment + transcript_with_speakers (JSON)
    b. aggregate_speakers_from_segments
       - Regroupe segments par speaker_label
       - Crée DetectedSpeaker pour chaque voix
       - Fallback SPEAKER_00 si AAI ne diarise pas (audio < 30s ou mono)
       - extract_speaker_sample : pydub découpe 8s du speaker → MP3
       - Upload vers MinIO bucket recordings
    c. suggest_participants_for_speakers (heuristique fuzzy noms dans transcript)
    d. status = waiting_speaker_mapping
    e. Notification email/in-app à l'utilisateur

[5] Utilisateur ouvre /meetings/{id}/recordings/{rid}/speakers
    - Liste DetectedSpeaker avec :
      * Label (SPEAKER_00, SPEAKER_01...)
      * Durée totale parlée
      * Nombre de segments
      * Sample audio (lecteur waveform)
      * Suggestion participant (fuzzy match)
      * Select tous les participants de la réunion

[6] Utilisateur écoute chaque extrait + sélectionne le participant
    → POST /recordings/{id}/speaker-mapping/ (bulk)

[7] Utilisateur clique "Confirmer et générer le CR"
    → POST /recordings/{id}/confirm-speakers/
    → generate_final_transcript_task : remplace SPEAKER_XX par display_name
    → summarize_recording_task :
       - format_transcript_for_llm (Markdown "Nom : phrase")
       - Anthropic Claude (primaire) → fallback DeepSeek
       - Génère résumé exécutif + minutes Markdown
    → extract_decisions_task : JSON structuré via LLM
    → extract_action_items_task : idem
    → Crée RecordingAIExtraction(status=DRAFT) pour chaque item

[8] status = completed, notification finale

[9] Utilisateur ouvre /meetings/{id}/recordings/{rid}/summary
    - Onglets : Résumé, Décisions, Actions, Transcription
    - Lecteur audio complet (waveform)
    - Cases à cocher sur décisions/actions

[10] Utilisateur valide N décisions/actions
     → POST /recordings/{id}/create-decisions/ avec extraction_ids[]
     → Crée objets réels dans decisions/ et action_plans/
     → status RecordingAIExtraction passe à PUSHED
```

---

## 4. MODÈLES DJANGO (`apps/meeting_recordings/models.py`)

### 4.1 Helpers de storage (CRITIQUE)

```python
from django.core.files.storage import storages

def _recordings_storage():
    """Retourne le storage dédié recordings (bucket séparé).

    ⚠️ CRITIQUE : tous les FileField audio DOIVENT utiliser ce storage
    pour qu'audio source + samples soient dans le MÊME bucket.
    Sinon : 404 sur les lectures (Django cherche dans le mauvais bucket).
    """
    try:
        return storages["recordings"]
    except Exception:
        return storages["default"]


def _audio_upload_path(instance, filename):
    org = instance.organization_id.hex if hasattr(instance.organization_id, 'hex') else instance.organization_id
    year = instance.created_at.year if instance.created_at else "_pending"
    return f"recordings/{org}/{year}/{instance.id}/{filename}"


def _speaker_sample_upload_path(instance, filename):
    rec = instance.recording
    org = rec.organization_id.hex if hasattr(rec.organization_id, 'hex') else rec.organization_id
    return f"recordings/{org}/samples/{rec.id}/{instance.speaker_label}_{filename}"
```

### 4.2 MeetingRecording (entité racine)

Champs essentiels :
- `meeting` FK → Meeting
- `recorded_by` FK → User
- `audio_file` FileField (storage=_recordings_storage, upload_to=_audio_upload_path)
- `original_filename`, `mime_type`, `file_size`, `duration_seconds`
- `status` CharField avec choices :
  ```
  CREATED, RECORDING, UPLOADING, UPLOADED, PROCESSING, TRANSCRIBING,
  DIARIZING, WAITING_SPEAKER_MAPPING, GENERATING_FINAL_TRANSCRIPT,
  SUMMARIZING, EXTRACTING_ACTIONS, COMPLETED, FAILED
  ```
- Horodatages : `started_at`, `stopped_at`, `uploaded_at`,
  `processing_started_at`, `processing_finished_at`
- `error_message` TextField (capture systématique des erreurs)
- `transcript_raw` TextField (sortie brute AAI)
- `transcript_with_speakers` JSONField (segments avant mapping)
- `transcript_final` JSONField (segments avec vrais noms)
- `summary` TextField (Markdown court)
- `ai_minutes` TextField (Markdown détaillé)
- `consent_acknowledged_at` DateTimeField (audit consentement)
- `deleted_audio_at` DateTimeField (purge rétention)

### 4.3 SpeakerSegment

- `recording` FK
- `speaker_label` CharField indexé ("SPEAKER_00", etc.)
- `start_time`, `end_time` Float
- `text` TextField
- `confidence` Float
- `audio_excerpt` FileField (storage=_recordings_storage)

### 4.4 DetectedSpeaker

- `recording` FK
- `speaker_label` CharField, unique_together avec recording
- `display_name` CharField (rempli après mapping)
- `sample_audio` FileField (storage=_recordings_storage, upload_to=_speaker_sample_upload_path)
- `total_segments`, `total_duration`, `confidence`
- `suggested_participant` FK → User (heuristique)
- `mapped_participant` FK → User (mapping confirmé)
- `is_confirmed` Bool

### 4.5 SpeakerParticipantMapping (audit historique)

- `recording`, `speaker_label`, `participant`, `confirmed_by`, `confirmed_at`, `notes`

### 4.6 RecordingAIExtraction (brouillons IA)

- `recording` FK
- `extraction_type` : SUMMARY, MINUTES, DECISION, ACTION, RISK, DEADLINE, BLOCKER
- `raw_payload` JSONField (structure variable par type)
- `status` : DRAFT, VALIDATED, REJECTED, PUSHED
- `created_decision`, `created_action_plan` FK (remplis après validation)
- `validated_by`, `validated_at`

---

## 5. SERVICES BACKEND (`apps/meeting_recordings/services/`)

Module par responsabilité (chaque fichier = un service métier testable isolément) :

### 5.1 `recording.py`
- `create_recording(meeting, user, title, consent_ack)` → MeetingRecording
- `update_status(rec, status, error="")` (idempotent, ne sort pas d'un statut terminal)
- `mark_uploaded(rec, file_obj, mime, duration)` :
  - Tente save() vers storage default
  - **Fallback FileSystem** si S3 plante (vers MEDIA_ROOT = /var/www/media)
- `mark_failed(rec, error)`

### 5.2 `audio_processing.py`
- `extract_speaker_sample(recording, speaker_label, segments, target_duration_sec=8)` :
  - Charge l'audio via pydub
  - Concatène les segments les plus longs jusqu'à target_duration_sec
  - **Fallback** : si pas de segments utilisables, prend les N premières secondes
  - Export MP3 64 kbps mono 22050 Hz
  - Retourne `ContentFile` ou None
- `get_audio_duration(file)` (utilitaire)
- `normalize_audio(recording)` (optionnel — wav 16kHz mono)

### 5.3 `transcription.py` ⚠️ POINTS CRITIQUES

```python
def transcribe_recording(recording):
    """
    POINTS CRITIQUES (pièges déjà rencontrés) :

    1. NE PAS passer d'URL publique à AssemblyAI
       → Télécharge l'audio en /tmp puis passe le PATH LOCAL au SDK
       → Évite la dépendance DNS / cert TLS / Traefik MinIO public
       → SDK assemblyai détecte path local et upload vers leur infra

    2. NE PAS spécifier speech_model
       → 'best' est déprécié, 'universal' parfois rejeté selon SDK version
       → Laisser le défaut serveur (AssemblyAI choisit le meilleur)
       → Si vraiment besoin : variable ASSEMBLYAI_MODEL en env

    3. speaker_labels=True ne marche QUE si audio ≥ 30s avec ≥ 2 voix distinctes
       → Sinon AAI renvoie transcript_raw mais utterances=[]
       → Le fallback diarisation crée 1 SPEAKER_00 dans ce cas

    4. Cleanup du fichier temp dans finally :
       if isinstance(audio_input, str) and audio_input.startswith("/tmp/"):
           try: os.unlink(audio_input)
           except: pass
    """
    aai = _build_aai_client()
    if aai is None:
        msg = "Client AssemblyAI indisponible"
        recording.error_message = msg
        recording.save(update_fields=["error_message", "updated_at"])
        return False

    audio_input = _download_audio_to_temp(recording)
    if audio_input is None:
        msg = "Impossible de télécharger l'audio depuis le storage"
        recording.error_message = msg
        recording.save(update_fields=["error_message", "updated_at"])
        return False

    try:
        config_kwargs = dict(
            language_code=getattr(settings, "ASSEMBLYAI_LANGUAGE", "fr"),
            speaker_labels=True,
            filter_profanity=False,
        )
        # Pas de speech_model par défaut
        config = aai.TranscriptionConfig(**config_kwargs)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_input)
        if transcript.status == aai.TranscriptStatus.error:
            recording.error_message = (transcript.error or "")[:2000]
            recording.save(update_fields=["error_message", "updated_at"])
            return False

        recording.transcript_raw = transcript.text or ""
        _persist_utterances(recording, transcript)  # crée SpeakerSegment
        recording.save(update_fields=["transcript_raw",
                                      "transcript_with_speakers", "updated_at"])
        return True
    except Exception as exc:
        recording.error_message = f"AAI: {exc}"[:2000]
        recording.save(update_fields=["error_message", "updated_at"])
        return False
    finally:
        import os
        if isinstance(audio_input, str) and audio_input.startswith("/tmp/"):
            try: os.unlink(audio_input)
            except: pass
```

### 5.4 `diarization.py`

- `aggregate_speakers_from_segments(recording)` :
  - Groupe SpeakerSegment par label
  - **Fallback SPEAKER_00** si aucun segment + duration > 0
  - Crée DetectedSpeaker
  - try/except autour de `extract_speaker_sample` (continue sur les autres si 1 échoue)
  - try/except autour de `ds.sample_audio.save()` (reset à None si upload S3 plante)
- `suggest_participants_for_speakers(recording)` :
  - Heuristique fuzzy : compte les mentions des noms participants dans transcript_raw
  - Greedy assignment 1-1
  - Stocke dans `suggested_participant` (NON `mapped_participant`)

### 5.5 `speaker_mapping.py`

- `map_speaker_to_participant(recording, speaker_label, participant, confirmed_by)` :
  - Met à jour DetectedSpeaker.mapped_participant + display_name
  - Crée ligne SpeakerParticipantMapping (audit)
- `confirm_all_mappings(recording, confirmed_by)` :
  - Vérifie que tous les speakers ont mapped_participant (sinon ValueError)
  - Marque is_confirmed=True
- `generate_final_transcript(recording)` :
  - Reconstruit transcript_final avec display_name au lieu de speaker_label
- `format_transcript_for_llm(recording, max_chars=60000)` :
  - Convertit en plain text "Nom : phrase\n" pour les prompts IA

### 5.6 `ai_summary.py`

Système avec **fallback Anthropic → DeepSeek** :

```python
def run_llm_with_fallback(*, system, user, max_tokens=4000):
    primary = getattr(settings, "RECORDING_AI_PRIMARY", "anthropic")
    fallback = getattr(settings, "RECORDING_AI_FALLBACK", "deepseek")

    providers = []
    for name in (primary, fallback):
        if name == "anthropic":
            providers.append(("anthropic", _call_anthropic))
        elif name == "deepseek":
            providers.append(("deepseek", _call_deepseek))

    for name, fn in providers:
        out = fn(system=system, user=user, max_tokens=max_tokens)
        if out:
            return out
        logger.warning("Provider %s indisponible — fallback", name)
    return None
```

Prompts essentiels :

```
SYSTEM_SUMMARY = "Tu es l'assistant exécutif du comité de direction (CODIR) de
{ORG}. Tu reçois la transcription HORODATÉE d'une réunion (nom du participant +
phrase prononcée). Produis un compte rendu de qualité exécutive, factuel, en
français professionnel. Règles : fidélité absolue à ce qui a été dit, pas
d'invention, phrases courtes, verbes actifs, distingue décisions/actions/risques."

USER_SUMMARY_TEMPLATE = """
Réunion : {meeting_title}
Date : {meeting_date}

TRANSCRIPTION :
{transcript}

PRODUIS LE COMPTE RENDU AU FORMAT MARKDOWN :
## Résumé exécutif (3-5 phrases)
## Points discutés (puces chronologiques)
## Décisions actées (1 puce par décision, formulation courte)
## Actions à mener (1 puce : "Faire X — Responsable : Nom — Échéance : date")
## Points bloquants / risques mentionnés
## Questions en suspens
"""

SYSTEM_EXTRACTION = """Tu es un extracteur structuré de décisions/actions.
Tu produis UNIQUEMENT du JSON valide, sans texte avant ou après. Tu n'inventes
JAMAIS — si une info manque, mets null."""

USER_EXTRACTION_TEMPLATE = """
Réunion : {meeting_title}
Participants connus : {participants}

TRANSCRIPTION :
{transcript}

Retourne EXACTEMENT ce JSON :
{
  "decisions": [{"title", "description", "category", "priority", "responsible_suggested", "deadline_suggested", "quote"}],
  "actions": [{"title", "description", "responsible_suggested", "deadline_suggested", "priority", "linked_decision", "quote"}],
  "risks": [{"title", "description", "quote"}],
  "blockers": [{"title", "description", "quote"}]
}
"""
```

Tolérance JSON :
```python
def _coerce_json(text):
    """Retire ```json ... ``` éventuels, garde { ... }, parse."""
    # ...
```

### 5.7 `extraction.py`

- `push_decision_to_module(extraction, validated_by)` → crée objet `Decision`
- `push_action_plan_to_module(extraction, validated_by, parent_decision=None)` →
  crée objet `ActionPlan` + `ActionTask`
- Heuristique `_resolve_user_by_name()` pour matcher le responsable suggéré

---

## 6. ENDPOINTS API REST

### Nested sous /meetings/{meeting_id}/recordings/
- `GET    /` — liste des recordings
- `POST   /start/` — créé l'enregistrement avant upload
- `POST   /upload/` — multipart audio + déclenche pipeline

### Flat sous /recordings/{id}/
- `GET    /` — détail (avec transcript + speakers + extractions)
- `GET    /status/` — polling léger (status + counts)
- `POST   /process/` — relance pipeline manuel
- `GET    /speakers/` — liste DetectedSpeaker
- `GET    /segments/` — liste SpeakerSegment
- `POST   /speaker-mapping/` — bulk mapping (`{mappings: [{speaker_label, participant_id, notes}]}`)
- `POST   /confirm-speakers/` — finalise mapping + chaîne pipeline IA
- `POST   /generate-final-transcript/`
- `POST   /generate-summary/`
- `POST   /extract-decisions/`
- `POST   /extract-actions/`
- `GET    /extractions/?type=...` — liste brouillons IA
- `POST   /create-decisions/` body `{extraction_ids: [...]}`
- `POST   /create-action-plans/` body `{extraction_ids: [...]}`

### Streaming audio (proxy depuis MinIO interne)
- `GET    /recordings/{id}/audio/?token=...` — audio complet
- `GET    /recordings/{id}/speakers/{label}/sample/?token=...` — extrait speaker

**⚠️ POINT CRITIQUE — token signé pour `<audio>` tags** :

Les balises HTML `<audio src=...>` n'envoient PAS de header `Authorization`.
Solution : HMAC signé éphémère en query string.

```python
# apps/meeting_recordings/audio_tokens.py
def generate_audio_token(*, resource_path, user_id, expiry_seconds=600):
    """HMAC-SHA256 sur (path + user + expiry), signé avec SECRET_KEY."""
    body = {"p": resource_path, "u": str(user_id), "e": int(time.time()) + expiry_seconds}
    body_bytes = json.dumps(body, separators=(",", ":")).encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), body_bytes, hashlib.sha256).digest()
    return f"{_b64url(body_bytes)}.{_b64url(sig)}"

def verify_audio_token(*, token, resource_path):
    # Vérifie sig + expiration + path → retourne payload ou None
```

Le serializer injecte automatiquement le token :
```python
def get_sample_audio_url(self, obj):
    if not obj.sample_audio: return None
    path = f"/api/v1/recordings/{obj.recording_id}/speakers/{obj.speaker_label}/sample/"
    token = generate_audio_token(resource_path=path,
                                  user_id=self.context["request"].user.id,
                                  expiry_seconds=30 * 60)
    return self.context["request"].build_absolute_uri(f"{path}?token={token}")
```

Le endpoint stream a `get_permissions` qui retourne `AllowAny` pour les streams
audio, et vérifie le token manuellement OU le Bearer JWT.

---

## 7. CELERY TASKS (`apps/meeting_recordings/tasks.py`)

```python
@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             autoretry_for=(IOError, OSError), retry_backoff=True)
def process_recording_task(self, recording_id):
    """Pipeline complet. Avec logs détaillés à chaque étape."""
    rec = _get(recording_id)
    if rec is None or rec.is_terminal:
        return "skipped"

    logger.info("▶ process_recording_task START rec=%s", recording_id)
    update_status(rec, RecordingStatus.PROCESSING)

    # 1. Transcription
    update_status(rec, RecordingStatus.TRANSCRIBING)
    try:
        ok = transcribe_recording(rec)
    except Exception as exc:
        logger.exception("transcribe failed")
        _fail(rec, f"Transcription: {type(exc).__name__}: {exc}")
        return "failed"
    if not ok:
        _fail(rec, rec.error_message or "Échec transcription")
        return "failed"

    # 2. Diarisation
    update_status(rec, RecordingStatus.DIARIZING)
    try:
        aggregate_speakers_from_segments(rec)
        suggest_participants_for_speakers(rec)
    except Exception as exc:
        _fail(rec, f"Diarisation: {type(exc).__name__}: {exc}")
        return "failed"

    # 3. Attente utilisateur
    update_status(rec, RecordingStatus.WAITING_SPEAKER_MAPPING)
    notify_speaker_mapping_required_task.delay(str(rec.id))
    return "waiting_mapping"
```

Routing Celery dans settings :
```python
CELERY_TASK_ROUTES = {
    "apps.meeting_recordings.tasks.*": {"queue": "recordings"},
}
```

⚠️ Le worker **doit écouter explicitement la queue `recordings`** :
```bash
celery -A config worker -Q default,celery,notifications,recordings
```

---

## 8. SETTINGS DJANGO

```python
# Storage S3/MinIO — DEUX storages distincts !
_S3_COMMON_OPTIONS = {
    "endpoint_url": env("S3_ENDPOINT", default="http://minio:9000"),
    "access_key": env("S3_ACCESS_KEY"),
    "secret_key": env("S3_SECRET_KEY"),
    "region_name": env("S3_REGION", default="eu-west-1"),
    "default_acl": "private",
    "file_overwrite": False,
    "addressing_style": "path",       # OBLIGATOIRE pour MinIO
    "signature_version": "s3v4",      # OBLIGATOIRE pour MinIO
    "custom_domain": env("S3_PUBLIC_DOMAIN", default=""),
    "url_protocol": env("S3_URL_PROTOCOL", default="https:"),
    "querystring_expire": env.int("S3_PRESIGN_EXPIRE", default=3600),
    # ⚠️ NE PAS ajouter ServerSideEncryption sur MinIO standalone !
    # MinIO ne supporte SSE qu'avec KMS configuré séparément.
    # → Si tu actives S3_SSE, ça plante avec "NotImplemented".
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**_S3_COMMON_OPTIONS, "bucket_name": env("S3_BUCKET")},
    },
    "staticfiles": {"BACKEND": "..."},
    "recordings": {  # ← CRITIQUE : bucket SÉPARÉ pour audio
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**_S3_COMMON_OPTIONS, "bucket_name": env("RECORDING_S3_BUCKET")},
    },
}

# Fallback FileSystem si S3 inaccessible
MEDIA_ROOT = env("MEDIA_ROOT", default="/var/www/media")  # ⚠️ DOIT être writable
MEDIA_URL = "/media/"

# Module recordings
ASSEMBLYAI_API_KEY = env("ASSEMBLYAI_API_KEY", default="")
ASSEMBLYAI_LANGUAGE = env("ASSEMBLYAI_LANGUAGE", default="fr")
ASSEMBLYAI_MODEL = env("ASSEMBLYAI_MODEL", default="")  # vide = défaut serveur

RECORDING_AI_PRIMARY = env("RECORDING_AI_PRIMARY", default="anthropic")
RECORDING_AI_FALLBACK = env("RECORDING_AI_FALLBACK", default="deepseek")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-4-5-20250929")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
DEEPSEEK_BASE_URL = env("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-chat")

MAX_RECORDING_UPLOAD_MB = env.int("MAX_RECORDING_UPLOAD_MB", default=600)
SPEAKER_SAMPLE_DURATION_SEC = env.int("SPEAKER_SAMPLE_DURATION_SEC", default=8)
RECORDING_S3_BUCKET = env("RECORDING_S3_BUCKET", default="meetings-recordings")
```

Permissions-Policy (à mettre dans Traefik OU nginx OU Django middleware) :
```
Permissions-Policy: camera=(), microphone=(self), geolocation=()
```
**⚠️ `()` vide bloque le micro. `(self)` autorise l'origine du site.**

---

## 9. FRONTEND REACT

### 9.1 Structure
```
src/features/meeting-recordings/
├── api.ts                          # axios wrappers typés
├── types/recording.types.ts        # types alignés DRF
├── hooks/
│   ├── useMediaRecorder.ts         # capture micro
│   ├── useRecordingUpload.ts       # upload multipart + progress
│   ├── useRecordingStatus.ts       # polling 3s, stop auto si terminal
│   ├── useSpeakerMapping.ts        # speakers + mappings
│   └── useRecordingExtraction.ts   # extractions IA
├── components/
│   ├── MeetingRecorderButton.tsx   # à inclure dans MeetingDetailPage
│   ├── RecordingControlPanel.tsx   # waveform animé pendant capture
│   ├── RecordingStatusBadge.tsx
│   ├── RecordingTimer.tsx
│   ├── RecordingUploadProgress.tsx
│   ├── AudioPermissionAlert.tsx
│   ├── SpeakerIdentificationPanel.tsx
│   ├── SpeakerCard.tsx
│   ├── SpeakerParticipantSelect.tsx
│   ├── SmartAudioPlayer.tsx        # waveform canvas + drag-to-seek
│   ├── TranscriptViewer.tsx
│   ├── FinalTranscriptEditor.tsx
│   ├── AISummaryPanel.tsx
│   ├── ExtractedDecisionsPanel.tsx
│   └── ExtractedActionsPanel.tsx
└── pages/
    ├── SpeakerMappingPage.tsx
    └── RecordingSummaryPage.tsx
```

### 9.2 useMediaRecorder — points critiques

```ts
// Format à privilégier (Chrome/Firefox)
const candidates = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
]

// getUserMedia avec contraintes pour qualité réunion
await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
})

// Garde-fou onbeforeunload pendant l'enregistrement
window.addEventListener('beforeunload', (e) => {
  if (state === 'recording' || state === 'paused') {
    e.preventDefault()
    e.returnValue = ''
  }
})

// MediaRecorder.start(timeslice=5000) pour chunks intermédiaires
// — permet upload streamé futur sans tout casser
```

### 9.3 SmartAudioPlayer — points critiques

```ts
// Calcule waveform statique via Web Audio API
async function computeWaveform(url, buckets = 80) {
  const res = await fetch(url, { credentials: 'omit' })
  const buf = await res.arrayBuffer()
  const ctx = new AudioContext()
  const audio = await ctx.decodeAudioData(buf)
  // ... échantillonne en N pics RMS
}

// Drag-to-seek + click-to-seek sur canvas
// Vitesse 1x / 1.25x / 1.5x / 2x via audio.playbackRate
// Raccourcis clavier : Space, ←, → (quand le composant a focus)
```

### 9.4 Token signé pour <audio>

Côté backend, l'URL est déjà signée et retournée par le serializer.
Côté frontend, on passe juste l'URL au tag — **JAMAIS** envoyer le JWT Bearer en query.

### 9.5 Intégration dans MeetingDetailPage

```tsx
import { MeetingRecorderButton } from '@/features/meeting-recordings/components/MeetingRecorderButton'

// Dans la page detail
<section className="px-10 py-8 border-t">
  <h3>Enregistrement & compte rendu IA</h3>
  <MeetingRecorderButton
    meetingId={meeting.id}
    existingRecording={latestRecording}
  />
</section>
```

### 9.6 Routes TanStack Router

```ts
createRoute({
  getParentRoute: () => shellRoute,
  path: '/meetings/$meetingId/recordings/$recordingId/speakers',
  component: SpeakerMappingPage,
})
createRoute({
  getParentRoute: () => shellRoute,
  path: '/meetings/$meetingId/recordings/$recordingId/summary',
  component: RecordingSummaryPage,
})
```

---

## 10. DOCKER-COMPOSE

```yaml
services:
  minio:
    image: minio/minio:RELEASE.2024-12-13T22-19-12Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:?must be set}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:?must be set}
      MINIO_REGION: ${S3_REGION:-eu-west-1}
      # MINIO_SERVER_URL / MINIO_BROWSER_REDIRECT_URL : vide tant que DNS pas prêt
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:9000/minio/health/live"]

  minio_init:
    image: minio/mc:RELEASE.2024-11-21T17-21-54Z
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      sh -c "
        mc alias set m http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD ;
        mc mb --ignore-existing m/$$S3_BUCKET ;
        mc mb --ignore-existing m/$$RECORDING_S3_BUCKET ;
        mc anonymous set none m/$$S3_BUCKET ;
        mc anonymous set none m/$$RECORDING_S3_BUCKET ;
      "

  worker:
    command: celery -A config worker -Q default,celery,notifications,recordings
    depends_on:
      minio:
        condition: service_healthy
      minio_init:
        condition: service_completed_successfully  # ← critique : attendre buckets
```

Dockerfile backend doit installer **ffmpeg** :
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
```

---

## 11. PIÈGES CRITIQUES À ÉVITER (issus du debug)

### 11.1 Permissions navigateur
- **Permissions-Policy: microphone=()** dans Traefik/nginx bloque l'accès micro AVANT getUserMedia.
- Fix : `microphone=(self)`

### 11.2 Routing DRF
- **`queryset = Model.objects.all()` au niveau classe** s'évalue à l'import, AVANT activation tenant context. → 404 systématique.
- Fix : utiliser `def get_queryset(self)`.

### 11.3 Storage S3
- **`S3_SSE=AES256`** dans .env active SSE-KMS, MinIO standalone n'accepte pas.
- Fix : laisser S3_SSE vide. Build conditionnel `object_parameters`.
- **`addressing_style="path"` + `signature_version="s3v4"`** OBLIGATOIRES pour MinIO.
- **2 storages distincts** : default (documents) + recordings (audio). Tous les
  FileField audio doivent pointer vers le storage `recordings` via `storage=` explicite.

### 11.4 Fallback storage
- Container Django avec `read_only: true` → seuls les volumes mountés sont writables.
- `MEDIA_ROOT = "/var/www/media"` (volume) PAS `BASE_DIR/"media"` (rootfs read-only).

### 11.5 Variables d'env Docker
- **`docker-compose.yml` contient des défauts hardcodés** dans des anchors comme `x-common-env`.
- Modifier `.env` ne suffit PAS si une variable a un défaut dans le compose.
- Vérifier avec `docker compose config | grep VARIABLE`.

### 11.6 AssemblyAI
- **`speech_model="best"` déprécié**, `"universal"` parfois rejeté selon version SDK.
- Fix : NE PAS spécifier speech_model du tout. Défaut serveur (universal-2 en 2026).
- **URL publique inaccessible** = AAI ne peut pas télécharger.
- Fix : download local + passe le path au SDK qui upload chez eux.
- **Diarisation activée seulement si audio ≥ 30s avec ≥ 2 voix distinctes.**
- Fix : fallback SPEAKER_00 si transcript_with_speakers est vide.

### 11.7 Audio HTML5
- **`<audio src>` n'envoie PAS de header Authorization**.
- Fix : token signé HMAC en query string `?token=...`.
- Endpoint stream : `get_permissions` retourne AllowAny + vérification token manuelle.

### 11.8 TanStack Query cache stale
- Après regénération backend, le frontend peut afficher d'anciens speakers.
- Fix : `staleTime: 5_000`, `refetchOnMount: 'always'`, `refetchOnWindowFocus: true`.

### 11.9 Docker rebuild
- **`docker compose up -d --force-recreate`** ne rebuild PAS l'image.
- Fix : toujours `docker compose build` AVANT `up -d --force-recreate` après modif Python.

### 11.10 Heredoc dans docker exec
- `docker compose exec` alloue un TTY par défaut → heredoc échoue.
- Fix : ajouter `-T` (disable TTY) : `docker compose exec -T service cmd << EOF`.

### 11.11 Dates frontend
- `format(new Date(null))` lance `RangeError: Invalid time value`.
- Fix : helper `safeFormat(value, fmt, opts)` qui retourne fallback si invalide.

---

## 12. CRITÈRES D'ACCEPTATION

Le module est validé si :

- [ ] L'utilisateur peut démarrer un enregistrement depuis le détail réunion
- [ ] L'audio est capturé en webm/opus, durée mesurée correctement
- [ ] Le Blob audio est uploadé en multipart sans 500/502
- [ ] Le pipeline transcrit l'audio via AssemblyAI sans erreur
- [ ] Les voix sont détectées et exposées sous forme SPEAKER_XX
- [ ] Pour chaque voix, un extrait MP3 ~8s est généré et stocké
- [ ] L'utilisateur peut écouter chaque extrait (token signé, sans auth header)
- [ ] L'utilisateur peut associer chaque voix à un participant
- [ ] Transcript final affiche les vrais noms à la place de SPEAKER_XX
- [ ] Claude/DeepSeek génère le résumé en Markdown structuré
- [ ] Décisions et actions sont extraites en JSON valide
- [ ] L'utilisateur valide N décisions → créées dans decisions/
- [ ] L'utilisateur valide N actions → créées dans action_plans/
- [ ] Notifications email + in-app à chaque étape clé
- [ ] Audit logs sur création, mapping, validation
- [ ] Logs détaillés à chaque étape du pipeline (debug facile)
- [ ] Fallback FileSystem si MinIO indisponible
- [ ] Fallback DeepSeek si Claude indisponible
- [ ] Fallback SPEAKER_00 si AAI ne diarise pas

---

## 13. VARIABLES D'ENV REQUISES

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
S3_PUBLIC_DOMAIN=storage.example.com    # optionnel — URLs présignées
S3_URL_PROTOCOL=https:
S3_PRESIGN_EXPIRE=3600
# NE PAS définir S3_SSE pour MinIO standalone

# Backups locaux
MEDIA_ROOT=/var/www/media

# IA
ASSEMBLYAI_API_KEY=xxx
ASSEMBLYAI_LANGUAGE=fr
# ASSEMBLYAI_MODEL=     # vide = défaut serveur (recommandé)

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
RECORDING_RAW_RETENTION_DAYS=90
```

---

## 14. CHECKLIST DÉPLOIEMENT

```bash
# 1. DNS
# Configurer storage-xxx.domain et codir-minio-console.domain → IP serveur

# 2. Variables d'env
# Copier .env.prod.example → .env.prod, remplir les secrets

# 3. Build images
docker compose -f docker-compose.prod.yml build --no-cache

# 4. Démarrer MinIO + buckets
docker compose -f docker-compose.prod.yml up -d minio
sleep 30
docker compose -f docker-compose.prod.yml up minio_init

# 5. Démarrer tout le stack
docker compose -f docker-compose.prod.yml up -d --force-recreate

# 6. Migrations
docker compose -f docker-compose.prod.yml exec -T web python manage.py migrate

# 7. Vérifications
# - MinIO healthy
# - Worker écoute la queue recordings
docker compose -f docker-compose.prod.yml exec -T worker celery -A config inspect active_queues

# - Storage Django fonctionne
docker compose -f docker-compose.prod.yml exec -T web python manage.py shell -c "
from django.core.files.storage import storages
from django.core.files.base import ContentFile
s = storages['recordings']
name = s.save('test.txt', ContentFile(b'ok'))
print('OK:', name)
s.delete(name)
"

# 8. Test end-to-end depuis l'UI
```

---

## 15. CONTRAINTES OBLIGATOIRES

1. **Ne JAMAIS prétendre identifier automatiquement un participant**. Le système
   propose, l'utilisateur valide. Le `mapped_participant` est rempli uniquement
   après action explicite.

2. **Bannière de consentement** affichée AVANT démarrage :
   « Cette réunion est enregistrée à des fins de compte rendu. Les participants
   doivent être informés avant le début de l'enregistrement. »
   Checkbox obligatoire avant déblocage du bouton "Démarrer".

3. **Permissions par rôle** : par défaut, tout membre actif du tenant peut
   enregistrer (cas bêta). Resserrer en prod via setting `RECORDING_RESTRICT_TO_PARTICIPANTS`.

4. **Audit logs** sur toutes les actions sensibles (création, upload, mapping,
   validation extraction).

5. **Code IA-généré DRAFT** : aucune Decision ni ActionPlan n'est créée
   sans validation manuelle explicite.

6. **Stream proxy Django** au lieu d'URL S3 publiques. Le bucket recordings
   reste privé. Aucun risque d'accès anonyme aux audios.

7. **Retention configurable** : `RECORDING_RAW_RETENTION_DAYS` permet la purge
   automatique des audios bruts après N jours.

---

## 16. TESTS À ÉCRIRE

```python
# apps/meeting_recordings/tests/

def test_create_recording_initial_status():
    rec = create_recording(meeting=meeting, recorded_by=user)
    assert rec.status == "created"

def test_upload_marks_status_uploaded():
    rec = create_recording(...)
    rec = mark_uploaded(rec, file_obj=audio_blob, ...)
    assert rec.status == "uploaded"
    assert rec.audio_file.name

def test_pipeline_process_recording_async(celery_app):
    # Mock AAI + Anthropic
    # Vérifie le workflow complet : transcribe → diarize → waiting_speaker_mapping

def test_token_signed_audio_valid():
    token = generate_audio_token(resource_path="/a/b/", user_id="u1", expiry_seconds=60)
    payload = verify_audio_token(token=token, resource_path="/a/b/")
    assert payload["u"] == "u1"

def test_token_expired_rejected():
    token = generate_audio_token(resource_path="/x", user_id="u1", expiry_seconds=-1)
    assert verify_audio_token(token=token, resource_path="/x") is None

def test_fallback_speaker_00_when_no_utterances():
    rec = create_recording_with_audio()
    rec.duration_seconds = 60
    rec.transcript_with_speakers = []  # AAI ne diarise pas
    aggregate_speakers_from_segments(rec)
    assert rec.speakers.count() == 1
    assert rec.speakers.first().speaker_label == "SPEAKER_00"
```

---

## 17. LIVRABLES ATTENDUS

À la fin de l'implémentation :

1. App Django `apps/meeting_recordings/` complète (21 fichiers : models, services,
   tasks, views, serializers, urls, permissions, audio_tokens, admin, signals,
   migration initiale)

2. Module React `features/meeting-recordings/` complet (23 fichiers : api, types,
   5 hooks, 15 composants, 2 pages)

3. Configuration Docker Compose mise à jour (services minio + minio_init,
   dépendances worker→minio, queue recordings)

4. Variables d'env documentées dans `.env.example` et `.env.prod.example`

5. Migration Django appliquée (6 tables)

6. Templates email pour notifications (welcome, mapping_required, completed, failed)

7. Tests unitaires de base (services + permissions + tokens)

8. README ou doc de déploiement avec checklist

9. Frontend Routes ajoutées dans le router principal :
   - `/meetings/$meetingId/recordings/$recordingId/speakers`
   - `/meetings/$meetingId/recordings/$recordingId/summary`

10. Intégration `MeetingRecorderButton` dans la page MeetingDetail existante

---

## FIN DU PROMPT

Si tu as des questions de clarification AVANT de coder (ex: structure d'auth
existante, modèle User, fournisseur IA déjà configuré), pose-les. Ensuite
implémente en suivant rigoureusement les sections 4 à 10, en évitant
systématiquement les pièges de la section 11.
