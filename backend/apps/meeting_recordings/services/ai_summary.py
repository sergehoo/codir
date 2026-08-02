"""MeetingAISummaryService — résumé + extraction décisions/actions.

Stratégie LLM :
- Provider primaire = Claude (Anthropic).
- Fallback automatique = DeepSeek (compat OpenAI SDK).
- Format de sortie strict JSON (validé) pour l'extraction structurée.
- Le résumé est en Markdown libre (texte exécutif).

L'utilisateur valide chaque extraction avant que ça crée un objet réel
dans decisions/action_plans. Tous les éléments restent au statut DRAFT
jusqu'à validation manuelle (cf RecordingAIExtraction).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from django.conf import settings

from ..models import (
    AIExtractionStatus, AIExtractionType,
    MeetingRecording, RecordingAIExtraction,
)
from .speaker_mapping import format_transcript_for_llm

logger = logging.getLogger(__name__)


# ─── Provider wrappers ─────────────────────────────────────────

def _call_anthropic(*, system: str, user: str, max_tokens: int = 4000) -> Optional[str]:
    """Appelle Claude via le SDK Anthropic. Retourne le texte ou None si erreur."""
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        logger.exception("anthropic SDK absent")
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatène tous les content blocks (Claude renvoie une liste)
        parts: list[str] = []
        for block in (msg.content or []):
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude appel KO : %s", exc)
        return None


def _call_deepseek(*, system: str, user: str, max_tokens: int = 4000) -> Optional[str]:
    """Appelle DeepSeek via le SDK OpenAI compat (base_url=DEEPSEEK_BASE_URL)."""
    api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.exception("openai SDK absent")
        return None
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        model = getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DeepSeek appel KO : %s", exc)
        return None


def run_llm_with_fallback(*, system: str, user: str, max_tokens: int = 4000) -> Optional[str]:
    """Tente Claude, puis DeepSeek si Claude indisponible.

    Retourne le texte de la réponse, ou None si TOUT a échoué (caller doit
    gérer l'erreur — généralement marque l'extraction failed).
    """
    primary = getattr(settings, "RECORDING_AI_PRIMARY", "anthropic")
    fallback = getattr(settings, "RECORDING_AI_FALLBACK", "deepseek")

    providers: list[tuple[str, Callable]] = []
    for name in (primary, fallback):
        if name == "anthropic":
            providers.append(("anthropic", _call_anthropic))
        elif name == "deepseek":
            providers.append(("deepseek", _call_deepseek))

    for name, fn in providers:
        out = fn(system=system, user=user, max_tokens=max_tokens)
        if out:
            logger.info("LLM réponse via %s (%d chars)", name, len(out))
            return out
        logger.warning("Provider %s indisponible — bascule fallback.", name)
    return None


# ─── Prompts ──────────────────────────────────────────────────

SYSTEM_SUMMARY = """Tu es l'assistant exécutif du comité de direction (CODIR) de Kaydan Groupe.
Tu reçois la transcription HORODATÉE d'une réunion CODIR (nom du participant + phrase prononcée).
Ta mission : produire un compte rendu de qualité exécutive, factuel, en français professionnel.

Règles absolues :
- Reste fidèle à ce qui a été dit. Ne fabrique aucune information.
- Distingue clairement : décisions actées, actions à mener, points de vigilance.
- Pas de jugement de valeur. Reste neutre.
- Style : phrases courtes, verbe à l'infinitif pour les actions, voix active.
- Si une information manque (échéance, responsable), écris « non précisé »."""

USER_SUMMARY_TEMPLATE = """Réunion : {meeting_title}
Date : {meeting_date}

TRANSCRIPTION :
{transcript}

PRODUIS LE COMPTE RENDU AU FORMAT MARKDOWN suivant :

## Résumé exécutif
3-5 phrases qui capturent l'essentiel.

## Points discutés
- Liste à puces, ordre chronologique.

## Décisions actées
- 1 puce par décision, formulation courte, qui a tranché si mentionné.

## Actions à mener
- 1 puce par action : « Faire X » — Responsable : Nom — Échéance : date ou « non précisé ».

## Points bloquants / risques mentionnés
- 1 puce par point. Vide si aucun.

## Questions en suspens
- 1 puce par question reportée. Vide si aucune."""


SYSTEM_EXTRACTION = """Tu es un extracteur structuré de décisions et d'actions à partir
d'une transcription de réunion CODIR. Tu produis UNIQUEMENT du JSON valide,
sans aucun texte avant ou après. Tu n'inventes JAMAIS d'informations.
Si une info n'est pas explicitement dans le transcript, tu mets null."""


USER_EXTRACTION_TEMPLATE = """Réunion : {meeting_title}
Participants connus (à utiliser pour le champ 'responsible_suggested') : {participants}

TRANSCRIPTION :
{transcript}

Retourne EXACTEMENT ce JSON (pas de markdown, pas de commentaires) :

{{
  "decisions": [
    {{
      "title": "Titre court de la décision (max 200 chars)",
      "description": "Reformulation de la décision en 1-2 phrases.",
      "category": "budget | strategy | RH | opérations | gouvernance | autre",
      "priority": "low | medium | high | critical",
      "responsible_suggested": "Nom complet du responsable cité (parmi les participants connus) ou null",
      "deadline_suggested": "YYYY-MM-DD si une date est citée, sinon null",
      "quote": "Citation exacte issue du transcript qui justifie cette décision"
    }}
  ],
  "actions": [
    {{
      "title": "Action à l'infinitif (max 200 chars) — ex: 'Préparer le budget 2027'",
      "description": "Détail en 1-2 phrases.",
      "responsible_suggested": "Nom complet (parmi les participants connus) ou null",
      "deadline_suggested": "YYYY-MM-DD ou null",
      "priority": "low | medium | high | critical",
      "linked_decision": "Titre de la décision liée (si action issue d'une décision) ou null",
      "quote": "Citation justificative exacte"
    }}
  ],
  "risks": [
    {{
      "title": "Risque mentionné (max 200 chars)",
      "description": "Description courte",
      "quote": "Citation exacte"
    }}
  ],
  "blockers": [
    {{
      "title": "Point bloquant",
      "description": "Description courte",
      "quote": "Citation"
    }}
  ]
}}

Si une catégorie est vide, retourne une liste vide []. Ne mets jamais null à la place d'un tableau."""


# ─── Helpers JSON tolérants ────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _coerce_json(text: str) -> Optional[dict]:
    """Tolère les LLMs qui entourent leur JSON de ```json ... ```."""
    if not text:
        return None
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    # Trim avant la 1re { et après la dernière }
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first < 0 or last < first:
        return None
    cleaned = cleaned[first:last + 1]
    try:
        return json.loads(cleaned)
    except Exception:  # noqa: BLE001
        return None


# ─── Public API ────────────────────────────────────────────────

def generate_summary(recording: MeetingRecording) -> Optional[str]:
    """Génère le résumé + minutes Markdown. Retourne le texte ou None."""
    transcript = format_transcript_for_llm(recording)
    if not transcript.strip():
        return None
    user_prompt = USER_SUMMARY_TEMPLATE.format(
        meeting_title=getattr(recording.meeting, "title", "Réunion CODIR"),
        meeting_date=(recording.meeting.scheduled_start.strftime("%Y-%m-%d")
                      if getattr(recording.meeting, "scheduled_start", None)
                      else "non précisée"),
        transcript=transcript,
    )
    text = run_llm_with_fallback(
        system=SYSTEM_SUMMARY, user=user_prompt, max_tokens=4000,
    )
    if not text:
        return None

    # ⚠ Lot HIST — avant d'écraser le CR existant, on l'archive en version.
    # Sans ça, une régénération détruit définitivement le CR précédent (et
    # toute correction manuelle qu'il contenait).
    had_previous = bool((recording.ai_minutes or "").strip()
                        or (recording.summary or "").strip())
    if had_previous:
        try:
            from .minutes_versioning import snapshot_current_minutes
            from ..models import MinutesVersionOrigin
            snapshot_current_minutes(
                recording=recording,
                origin=MinutesVersionOrigin.AI_REGENERATED,
                label="Avant régénération IA",
            )
        except Exception:  # noqa: BLE001
            # Best-effort : ne jamais bloquer la génération sur l'historisation.
            logger.exception(
                "generate_summary: snapshot version KO (rec=%s)", recording.id,
            )

    # On stocke le tout dans summary + ai_minutes (même contenu structuré
    # markdown — on peut les séparer plus tard).
    recording.ai_minutes = text
    # Pour le summary "court", on tente d'extraire la section "Résumé exécutif".
    short = _extract_section(text, "Résumé exécutif")
    recording.summary = short or text[:1000]
    recording.save(update_fields=["summary", "ai_minutes", "updated_at"])

    # Trace la nouvelle version produite (première génération ou régénération).
    try:
        from .minutes_versioning import snapshot_current_minutes
        from ..models import MinutesVersionOrigin
        snapshot_current_minutes(
            recording=recording,
            origin=(MinutesVersionOrigin.AI_REGENERATED if had_previous
                    else MinutesVersionOrigin.AI_GENERATED),
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "generate_summary: snapshot post-génération KO (rec=%s)", recording.id,
        )

    # Enregistre aussi un brouillon SUMMARY dans RecordingAIExtraction
    RecordingAIExtraction.unscoped.filter(
        recording=recording, extraction_type=AIExtractionType.SUMMARY,
    ).delete()
    RecordingAIExtraction.unscoped.create(
        organization=recording.organization,
        recording=recording,
        extraction_type=AIExtractionType.SUMMARY,
        raw_payload={"markdown": text},
        status=AIExtractionStatus.DRAFT,
    )

    # ⚡ Lot 5 — Détection d'engagements oraux (best-effort, non-bloquant).
    # Crée des AIActionRequest type=create_action_task pour les engagements
    # détectés. L'utilisateur valide depuis le sidebar IA.
    try:
        from django.conf import settings as _settings
        if getattr(_settings, "RECORDING_COMMITMENT_DETECTION_ENABLED", True):
            from .commitment_detection import detect_commitments
            summary = detect_commitments(recording)
            logger.info("Commitments detected for recording %s: %s",
                        recording.id, summary)
    except Exception:  # noqa: BLE001
        logger.exception("commitment_detection KO (non-bloquant)")

    return text


def _extract_section(markdown: str, section_title: str) -> str:
    """Récupère le contenu d'une section ## donnée jusqu'au prochain ##."""
    pattern = re.compile(
        rf"##\s+{re.escape(section_title)}\s*\n(.*?)(?=\n##\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(markdown)
    return m.group(1).strip() if m else ""


def extract_decisions(recording: MeetingRecording) -> list[RecordingAIExtraction]:
    """Extrait les décisions sous forme de brouillons RecordingAIExtraction(DRAFT)."""
    return _extract_structured(
        recording, extraction_types=[AIExtractionType.DECISION],
    )


def extract_action_items(recording: MeetingRecording) -> list[RecordingAIExtraction]:
    """Extrait les actions sous forme de brouillons (DRAFT)."""
    return _extract_structured(
        recording, extraction_types=[AIExtractionType.ACTION],
    )


def _extract_structured(
    recording: MeetingRecording, extraction_types: list[str],
) -> list[RecordingAIExtraction]:
    """Appelle le LLM en mode JSON, mappe les items vers RecordingAIExtraction."""
    transcript = format_transcript_for_llm(recording)
    if not transcript.strip():
        return []

    # Liste des participants pour aider le LLM à proposer un responsable plausible
    try:
        participants = list(
            recording.meeting.participants.select_related("user")
            .filter(user__isnull=False)
            .values_list("user__first_name", "user__last_name")
        )
        names = ", ".join(
            f"{fn or ''} {ln or ''}".strip() for fn, ln in participants if (fn or ln)
        ) or "non communiqués"
    except Exception:  # noqa: BLE001
        names = "non communiqués"

    user_prompt = USER_EXTRACTION_TEMPLATE.format(
        meeting_title=getattr(recording.meeting, "title", "Réunion CODIR"),
        participants=names,
        transcript=transcript,
    )
    raw = run_llm_with_fallback(
        system=SYSTEM_EXTRACTION, user=user_prompt, max_tokens=4000,
    )
    payload = _coerce_json(raw or "") or {}

    # Wipe anciens drafts du même type pour ne pas dupliquer sur re-run.
    RecordingAIExtraction.unscoped.filter(
        recording=recording,
        extraction_type__in=extraction_types,
        status=AIExtractionStatus.DRAFT,
    ).delete()

    out: list[RecordingAIExtraction] = []
    if AIExtractionType.DECISION in extraction_types:
        for d in payload.get("decisions", []) or []:
            ext = RecordingAIExtraction.unscoped.create(
                organization=recording.organization,
                recording=recording,
                extraction_type=AIExtractionType.DECISION,
                raw_payload=d,
                status=AIExtractionStatus.DRAFT,
            )
            out.append(ext)
    if AIExtractionType.ACTION in extraction_types:
        for a in payload.get("actions", []) or []:
            ext = RecordingAIExtraction.unscoped.create(
                organization=recording.organization,
                recording=recording,
                extraction_type=AIExtractionType.ACTION,
                raw_payload=a,
                status=AIExtractionStatus.DRAFT,
            )
            out.append(ext)
    # Risques + blockers : on les pose en brouillon pour info, sans push automatique.
    for r in payload.get("risks", []) or []:
        RecordingAIExtraction.unscoped.create(
            organization=recording.organization,
            recording=recording,
            extraction_type=AIExtractionType.RISK,
            raw_payload=r,
            status=AIExtractionStatus.DRAFT,
        )
    for b in payload.get("blockers", []) or []:
        RecordingAIExtraction.unscoped.create(
            organization=recording.organization,
            recording=recording,
            extraction_type=AIExtractionType.BLOCKER,
            raw_payload=b,
            status=AIExtractionStatus.DRAFT,
        )
    return out
