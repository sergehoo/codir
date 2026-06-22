"""Détection d'engagements oraux — Lot 5.

À partir du transcript diarisé d'une réunion, l'IA extrait les phrases du
type "je m'en occupe avant vendredi" / "Marc gère le sujet X" / "j'envoie
le doc demain" et les transforme en propositions de tâches que l'utilisateur
peut confirmer en un clic dans le sidebar IA.

Pipeline :
  1. `detect_commitments(recording)` lit le transcript + le mapping
     speaker→user existant.
  2. Appel LLM (Claude prioritaire, DeepSeek fallback) avec un prompt
     structuré qui retourne du JSON strict.
  3. `_parse_commitments_json()` valide et nettoie.
  4. `_resolve_assignee()` mappe speaker_label OU nom prononcé → User.
  5. `_emit_action_requests()` crée des `AIActionRequest(action_type=
     "create_action_task", status=pending)` qui apparaissent dans le
     sidebar IA pour validation humaine.

Coût LLM : ~1 appel par CR (15-30k tokens en entrée, ≤2k en sortie).
À tarifs Claude Sonnet 4 : ~0.06$ par réunion d'1h.

Désactivable via `RECORDING_COMMITMENT_DETECTION_ENABLED=False`.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Prompt LLM ────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Tu es un assistant exécutif qui analyse les comptes rendus de comité de "
    "direction. Ton rôle : identifier les ENGAGEMENTS ORAUX explicites — "
    "c'est-à-dire les moments où un participant déclare qu'il va personnellement "
    "exécuter une action concrète, avec ou sans deadline.\n\n"
    "Ne RETIENS PAS :\n"
    "- les opinions, réflexions, hypothèses\n"
    "- les décisions collectives ou approuvées par vote (déjà traitées ailleurs)\n"
    "- les questions ouvertes\n"
    "- les engagements vagues sans verbe d'action clair\n\n"
    "RETIENS uniquement :\n"
    "- phrases du type \"je m'en occupe\", \"je gère\", \"je prépare\", "
    "\"j'envoie\", \"je relance\", \"je valide avec X\"\n"
    "- les engagements pris au nom d'une 3e personne nommément citée : "
    "\"Marc va s'occuper de…\", \"Sophie prépare…\""
)

USER_PROMPT_TEMPLATE = """Voici un transcript de réunion CODIR avec diarisation par speaker.

PARTICIPANTS IDENTIFIÉS :
{participants_block}

TRANSCRIPT :
{transcript}

CONSIGNE : Retourne UNIQUEMENT un tableau JSON valide (pas de markdown, pas de prose
autour) de la forme suivante :

[
  {{
    "speaker_label": "SPEAKER_00",
    "assignee_name": "Marc Dupont",
    "action": "Préparer la présentation budget Q3 pour le prochain CODIR",
    "due_phrase": "avant vendredi",
    "due_date_iso": "{next_friday}",
    "confidence": 0.85,
    "evidence_quote": "Je m'en occupe et je vous envoie ça avant vendredi"
  }}
]

Règles :
- `speaker_label` : copie le label exact (SPEAKER_XX) du locuteur qui s'engage.
- `assignee_name` : nom complet si tu peux le résoudre depuis les participants ;
  sinon laisse `null`.
- `action` : reformule en phrase claire et autoportante (max 200 caractères).
- `due_phrase` : ce qui est dit dans le transcript ("avant vendredi", "la
  semaine prochaine", ou "" si pas de deadline).
- `due_date_iso` : convertis en date ISO YYYY-MM-DD si tu peux raisonnablement
  (date d'aujourd'hui : {today}). Sinon `null`.
- `confidence` : 0.0 à 1.0 selon ton degré de certitude.
- `evidence_quote` : citation textuelle (max 200 chars) qui justifie l'engagement.

Si tu ne détectes AUCUN engagement, renvoie `[]`. Maximum 10 engagements."""


# ─── Service principal ─────────────────────────────────────────

def detect_commitments(recording) -> dict:
    """Pipeline complet pour une recording.

    Returns: {"created": N, "skipped": N, "errors": [...]}
    """
    summary = {"created": 0, "skipped": 0, "errors": []}

    if not getattr(settings, "RECORDING_COMMITMENT_DETECTION_ENABLED", True):
        summary["skipped"] = 1
        summary["errors"].append("Désactivé via settings")
        return summary

    transcript = (recording.transcript_raw or "").strip()
    if not transcript:
        summary["errors"].append("Transcript vide")
        return summary

    # Construit le bloc participants pour le prompt
    participants_block = _build_participants_block(recording)
    if not participants_block:
        summary["skipped"] += 1
        summary["errors"].append("Aucun participant mappé — détection sautée")
        return summary

    # Appel LLM (Claude prioritaire)
    today = timezone.localdate().isoformat()
    next_friday = _next_weekday(timezone.localdate(), 4).isoformat()  # 4 = vendredi
    user_prompt = USER_PROMPT_TEMPLATE.format(
        participants_block=participants_block,
        transcript=transcript[:60000],  # cap pour rester sous la limite Claude
        today=today,
        next_friday=next_friday,
    )

    raw_response = _call_llm(SYSTEM_PROMPT, user_prompt)
    if not raw_response:
        summary["errors"].append("LLM indisponible (Claude+DeepSeek KO)")
        return summary

    commitments = _parse_commitments_json(raw_response)
    if not commitments:
        summary["errors"].append("Aucun engagement détecté ou JSON invalide")
        return summary

    # Crée les AIActionRequest
    for c in commitments[:10]:
        try:
            created = _emit_action_request(recording, c)
            if created:
                summary["created"] += 1
            else:
                summary["skipped"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Commitment emit KO")
            summary["errors"].append(f"{type(exc).__name__}: {exc}")

    logger.info(
        "commitment_detection recording=%s created=%d skipped=%d errors=%d",
        recording.id, summary["created"], summary["skipped"], len(summary["errors"]),
    )
    return summary


# ─── Construction du bloc participants ─────────────────────────

def _build_participants_block(recording) -> str:
    """Liste les speakers identifiés du recording pour aider le LLM."""
    speakers = recording.speakers.select_related("mapped_participant").all()
    if not speakers:
        return ""
    lines = []
    for sp in speakers:
        name = ""
        if sp.mapped_participant_id:
            full = (
                sp.mapped_participant.get_full_name()
                if hasattr(sp.mapped_participant, "get_full_name")
                else sp.mapped_participant.email
            )
            name = full or sp.mapped_participant.email
        elif sp.display_name:
            name = sp.display_name
        else:
            name = "(non identifié)"
        lines.append(f"- {sp.speaker_label} = {name}")
    return "\n".join(lines)


# ─── Helper : prochain jour de semaine donné ───────────────────

def _next_weekday(d: date, weekday: int) -> date:
    """Retourne la prochaine date où weekday() == X (0=lundi…6=dimanche)."""
    days_ahead = (weekday - d.weekday() + 7) % 7
    return d + timedelta(days=days_ahead or 7)


# ─── Appel LLM (Claude prioritaire, DeepSeek fallback) ─────────

def _call_llm(system: str, user: str) -> str:
    """Appel LLM bref pour extraction structurée. Fallback gracieux."""
    # Claude
    api_key = (
        getattr(settings, "ANTHROPIC_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if resp and resp.content:
                return (resp.content[0].text or "").strip()
        except Exception:  # noqa: BLE001
            logger.exception("Claude commitment KO, fallback DeepSeek")

    # DeepSeek (OpenAI compatible)
    ds_key = (
        getattr(settings, "DEEPSEEK_API_KEY", "")
        or os.environ.get("DEEPSEEK_API_KEY", "")
    )
    if ds_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=ds_key,
                base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            resp = client.chat.completions.create(
                model=getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            if resp and resp.choices:
                return (resp.choices[0].message.content or "").strip()
        except Exception:  # noqa: BLE001
            logger.exception("DeepSeek commitment KO")

    return ""


# ─── Parsing du JSON LLM ───────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"\[\s*\{.*\}\s*\]", re.DOTALL)


def _parse_commitments_json(raw: str) -> list[dict]:
    """Extrait et valide le tableau JSON depuis la réponse LLM.

    Robuste aux préfixes/suffixes (le LLM rajoute parfois du texte malgré
    les consignes). Filtre les entrées invalides.
    """
    if not raw:
        return []
    # Tente parse direct
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return _validate_commitments(data)
    except (json.JSONDecodeError, ValueError):
        pass
    # Tente extraction du premier bloc JSON tableau
    m = _JSON_BLOCK_RE.search(raw)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return _validate_commitments(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _validate_commitments(items: list) -> list[dict]:
    """Garde uniquement les commitments avec champs requis valides."""
    valid = []
    for it in items:
        if not isinstance(it, dict):
            continue
        action = (it.get("action") or "").strip()
        if len(action) < 5:
            continue
        # Confidence : défaut 0.5
        conf = it.get("confidence")
        try:
            conf = float(conf) if conf is not None else 0.5
        except (TypeError, ValueError):
            conf = 0.5
        # Filtre les confidences trop basses (bruit)
        if conf < 0.4:
            continue
        # Due date : normalize ISO ou None
        due_iso = it.get("due_date_iso")
        if due_iso:
            try:
                datetime.fromisoformat(str(due_iso))
            except (TypeError, ValueError):
                due_iso = None
        valid.append({
            "speaker_label":  (it.get("speaker_label") or "").strip()[:40],
            "assignee_name":  (it.get("assignee_name") or "").strip()[:120] or None,
            "action":         action[:300],
            "due_phrase":     (it.get("due_phrase") or "").strip()[:80],
            "due_date_iso":   due_iso,
            "confidence":     round(conf, 2),
            "evidence_quote": (it.get("evidence_quote") or "").strip()[:300],
        })
    return valid


# ─── Resolver speaker → User ───────────────────────────────────

def _resolve_assignee(recording, commitment: dict):
    """Match un commitment vers un User assignable.

    Priorité :
      1. speaker_label → DetectedSpeaker.mapped_participant
      2. assignee_name fuzzy match contre User.first_name / last_name / email
         des memberships de l'org
    """
    speaker_label = commitment.get("speaker_label", "")
    if speaker_label:
        sp = recording.speakers.filter(speaker_label=speaker_label).first()
        if sp and sp.mapped_participant_id:
            return sp.mapped_participant

    name = (commitment.get("assignee_name") or "").strip().lower()
    if name:
        try:
            from apps.accounts.models import Membership
            org = recording.organization
            memberships = (
                Membership.unscoped
                .filter(organization=org, is_active=True)
                .select_related("user")
            )
            # Match exact "Prénom Nom" puis fuzzy
            for m in memberships:
                u = m.user
                full = (
                    u.get_full_name() if hasattr(u, "get_full_name") else u.email
                ).lower()
                if name == full or name in full or full in name:
                    return u
        except Exception:  # noqa: BLE001
            logger.exception("Fuzzy assignee match KO")
    return None


# ─── Création d'AIActionRequest ────────────────────────────────

def _emit_action_request(recording, commitment: dict) -> bool:
    """Crée un AIActionRequest pour validation humaine.

    Returns True si créé, False si déjà existant (dédup par evidence_quote).
    """
    from apps.ai_engine.models import AIActionRequest

    assignee = _resolve_assignee(recording, commitment)
    assignee_email = assignee.email if assignee else None
    org = recording.organization

    # Dédup : si une AIActionRequest existe déjà avec la même action sur ce
    # recording, on ne re-crée pas (cas du re-run de la détection).
    existing = AIActionRequest.unscoped.filter(
        organization=org,
        action_type="create_action_task",
        payload__source_recording_id=str(recording.id),
        payload__evidence_quote=commitment.get("evidence_quote", ""),
    ).first()
    if existing:
        return False

    # Le requesté est le créateur du recording, ou le 1er admin de l'org
    requested_by = recording.created_by or _fallback_org_admin(org)
    if not requested_by:
        logger.warning("No requested_by user for commitment, skipping")
        return False

    summary_text = f"Engagement détecté ({commitment['speaker_label']}) : "
    summary_text += commitment["action"][:120]

    payload = {
        "title":           commitment["action"],
        "description":     (
            f"📝 Engagement oral détecté en réunion.\n\n"
            f"**Locuteur** : {commitment['speaker_label']}\n"
            f"**Citation** : « {commitment.get('evidence_quote', '')} »\n"
            f"**Échéance déclarée** : {commitment.get('due_phrase') or '—'}\n"
            f"**Confiance IA** : {int(commitment['confidence'] * 100)}%"
        ),
        "assignee_email":  assignee_email,
        "due_date":        commitment.get("due_date_iso"),
        "priority":        "medium",
        # Métadonnées pour traçabilité + dédup
        "source_recording_id": str(recording.id),
        "source_meeting_id":   str(recording.meeting_id) if recording.meeting_id else "",
        "evidence_quote":      commitment.get("evidence_quote", ""),
        "speaker_label":       commitment["speaker_label"],
    }

    AIActionRequest.unscoped.create(
        organization=org,
        requested_by=requested_by,
        action_type="create_action_task",
        payload=payload,
        summary=summary_text[:300],
        status="pending",
    )
    return True


def _fallback_org_admin(org):
    """Trouve un user admin de l'org (owner ou executive) — fallback pour
    `requested_by` quand recording.created_by est null (legacy data)."""
    try:
        from apps.accounts.models import Membership
        m = (
            Membership.unscoped
            .filter(organization=org, is_active=True, is_owner=True)
            .select_related("user")
            .first()
        )
        if m:
            return m.user
        m = (
            Membership.unscoped
            .filter(organization=org, is_active=True, is_executive=True)
            .select_related("user")
            .first()
        )
        return m.user if m else None
    except Exception:  # noqa: BLE001
        return None
