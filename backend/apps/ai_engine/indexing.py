"""Service d'indexation sémantique pour la recherche cross-modules.

Stratégie :
  - Pour chaque objet métier (decision, plan, meeting, transcript, document),
    on extrait un texte représentatif (`title + description + ...`) et on le
    pousse dans `SemanticIndex` avec son embedding.
  - `text_hash` permet de skip l'embedding si le texte n'a pas changé.
  - Branché via signals `post_save` sur les modèles surveillés — l'index
    se maintient automatiquement au gré des édits métier.
  - Management command `reindex_semantic` pour le bootstrap initial ou
    après upgrade du modèle d'embedding.

Coût opérationnel :
  - ~10ms d'embedding par objet édité (CPU local, négligeable)
  - Pas de coût API externe.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction

logger = logging.getLogger(__name__)


# ─── Extraction du texte indexable par type d'objet ───────────

def _extract_decision(obj) -> dict:
    desc = (getattr(obj, "description_md", "") or "")[:4000]
    parts = [
        getattr(obj, "title", "") or "",
        desc,
    ]
    return {
        "title": (getattr(obj, "title", "") or "(sans titre)")[:300],
        "text": "\n".join(p for p in parts if p),
        "url": f"/decisions/{obj.id}",
    }


def _extract_plan(obj) -> dict:
    desc = (getattr(obj, "description_md", "") or "")[:4000]
    return {
        "title": (getattr(obj, "title", "") or "(sans titre)")[:300],
        "text": "\n".join(p for p in [getattr(obj, "title", ""), desc] if p),
        "url": f"/action-plans/{obj.id}",
    }


def _extract_meeting(obj) -> dict:
    summary = (getattr(obj, "summary", "") or "")[:4000]
    return {
        "title": (getattr(obj, "title", "") or "(sans titre)")[:300],
        "text": "\n".join(p for p in [getattr(obj, "title", ""), summary] if p),
        "url": f"/meetings/{obj.id}",
    }


def _extract_transcript(obj) -> dict:
    # On indexe ai_minutes (CR formaté) ou transcript_raw en fallback.
    text = (getattr(obj, "ai_minutes", "") or getattr(obj, "summary", "") or "")
    if not text:
        text = (getattr(obj, "transcript_raw", "") or "")
    text = text[:8000]
    meeting = getattr(obj, "meeting", None)
    title = (
        f"CR — {meeting.title}" if meeting else "Compte rendu"
    )[:300]
    return {
        "title": title,
        "text": text,
        "url": f"/meetings/{meeting.id}/recordings/{obj.id}/summary" if meeting else "",
    }


def _extract_document(obj) -> dict:
    title = (getattr(obj, "title", "") or getattr(obj, "name", "") or "Document")[:300]
    body = (getattr(obj, "content_text", "") or getattr(obj, "description", "") or "")[:6000]
    return {
        "title": title,
        "text": body or title,
        "url": f"/documents/{obj.id}",
    }


EXTRACTORS = {
    "decision":   _extract_decision,
    "plan":       _extract_plan,
    "meeting":    _extract_meeting,
    "transcript": _extract_transcript,
    "document":   _extract_document,
}


def index_object(*, obj, source_type: str, organization=None) -> Optional[str]:
    """Indexe (ou met à jour) un objet métier dans SemanticIndex.

    Returns: status `created` | `updated` | `unchanged` | `skipped` | `error`
    """
    from .embedding import embed_text, text_hash, MODEL_VERSION_TAG
    from .models import SemanticIndex

    extractor = EXTRACTORS.get(source_type)
    if not extractor:
        return "skipped"

    try:
        info = extractor(obj)
    except Exception:  # noqa: BLE001
        logger.exception("Extractor KO source_type=%s id=%s", source_type, getattr(obj, "id", "?"))
        return "error"

    text = (info.get("text") or "").strip()
    if not text:
        # Pas de texte exploitable → on retire l'index existant si présent
        SemanticIndex.unscoped.filter(source_type=source_type, source_id=str(obj.id)).delete()
        return "skipped"

    org = organization or getattr(obj, "organization", None)
    if org is None:
        return "skipped"

    new_hash = text_hash(text)
    existing = (
        SemanticIndex.unscoped
        .filter(source_type=source_type, source_id=str(obj.id))
        .first()
    )

    # Skip si hash inchangé ET même version de modèle (rien à faire)
    if existing and existing.text_hash == new_hash and existing.model_version == MODEL_VERSION_TAG:
        return "unchanged"

    # Calcul embedding (peut être lent au premier appel — modèle load)
    vec = embed_text(text)
    if vec is None:
        logger.warning("Embedding indispo — index sauté pour %s:%s", source_type, obj.id)
        return "error"

    with transaction.atomic():
        if existing:
            existing.organization = org
            existing.title = info.get("title", "")[:300]
            existing.text = text
            existing.text_hash = new_hash
            existing.embedding = vec
            existing.model_version = MODEL_VERSION_TAG
            existing.url = info.get("url", "")[:300]
            existing.save()
            return "updated"
        SemanticIndex.unscoped.create(
            organization=org,
            source_type=source_type,
            source_id=str(obj.id),
            title=info.get("title", "")[:300],
            text=text,
            text_hash=new_hash,
            embedding=vec,
            model_version=MODEL_VERSION_TAG,
            url=info.get("url", "")[:300],
        )
    return "created"


# ─── Signals (auto-indexation) ────────────────────────────────

def install_signals():
    """Branche les signals post_save pour maintenir l'index automatiquement.

    Appelé depuis `AiEngineConfig.ready()`.
    """
    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver

    # Decision
    try:
        from apps.decisions.models import Decision

        @receiver(post_save, sender=Decision, dispatch_uid="semantic_index_decision")
        def _on_decision_save(sender, instance, **kwargs):
            try:
                index_object(obj=instance, source_type="decision")
            except Exception:  # noqa: BLE001
                logger.exception("auto-index decision KO")

        @receiver(post_delete, sender=Decision, dispatch_uid="semantic_delete_decision")
        def _on_decision_delete(sender, instance, **kwargs):
            _delete_index(source_type="decision", source_id=str(instance.id))
    except ImportError:
        pass

    # ActionPlan
    try:
        from apps.action_plans.models import ActionPlan

        @receiver(post_save, sender=ActionPlan, dispatch_uid="semantic_index_plan")
        def _on_plan_save(sender, instance, **kwargs):
            try:
                index_object(obj=instance, source_type="plan")
            except Exception:  # noqa: BLE001
                logger.exception("auto-index plan KO")

        @receiver(post_delete, sender=ActionPlan, dispatch_uid="semantic_delete_plan")
        def _on_plan_delete(sender, instance, **kwargs):
            _delete_index(source_type="plan", source_id=str(instance.id))
    except ImportError:
        pass

    # Meeting
    try:
        from apps.meetings.models import Meeting

        @receiver(post_save, sender=Meeting, dispatch_uid="semantic_index_meeting")
        def _on_meeting_save(sender, instance, **kwargs):
            try:
                index_object(obj=instance, source_type="meeting")
            except Exception:  # noqa: BLE001
                logger.exception("auto-index meeting KO")

        @receiver(post_delete, sender=Meeting, dispatch_uid="semantic_delete_meeting")
        def _on_meeting_delete(sender, instance, **kwargs):
            _delete_index(source_type="meeting", source_id=str(instance.id))
    except ImportError:
        pass

    # MeetingRecording (transcript)
    try:
        from apps.meeting_recordings.models import MeetingRecording

        @receiver(post_save, sender=MeetingRecording, dispatch_uid="semantic_index_transcript")
        def _on_recording_save(sender, instance, **kwargs):
            try:
                index_object(obj=instance, source_type="transcript")
            except Exception:  # noqa: BLE001
                logger.exception("auto-index transcript KO")
    except ImportError:
        pass


def _delete_index(*, source_type: str, source_id: str):
    """Supprime l'entrée d'index quand l'objet métier est supprimé."""
    try:
        from .models import SemanticIndex
        SemanticIndex.unscoped.filter(
            source_type=source_type, source_id=source_id,
        ).delete()
    except Exception:  # noqa: BLE001
        logger.exception("delete index KO %s:%s", source_type, source_id)


# ─── Recherche sémantique ──────────────────────────────────────

def search(*, organization, query: str, limit: int = 20,
           kinds: Optional[list[str]] = None,
           min_similarity: float = 0.25) -> list[dict]:
    """Recherche sémantique dans l'org. Retourne top-K résultats.

    Args:
        organization: tenant courant — JAMAIS optionnel pour sécurité
        query: requête en langage naturel
        limit: max résultats (default 20)
        kinds: filtrer par types (ex. ["decision", "plan"])
        min_similarity: score minimum (0..1) — sous ce seuil on coupe

    Returns:
        Liste de dicts triés par similarity décroissante :
            {kind, id, title, snippet, url, similarity}
    """
    from .embedding import cosine_similarity, embed_text
    from .models import SemanticIndex

    if not query or not query.strip():
        return []

    q_vec = embed_text(query)
    if q_vec is None:
        return []

    qs = SemanticIndex.unscoped.filter(organization=organization)
    if kinds:
        qs = qs.filter(source_type__in=kinds)

    # Calcul similarity en mémoire — OK jusqu'à ~10k items. Au-delà, passer
    # à pgvector + index ivfflat (changement de champ + index SQL).
    scored = []
    for item in qs.iterator(chunk_size=500):
        emb = item.embedding
        if not emb or not isinstance(emb, list):
            continue
        sim = cosine_similarity(q_vec, emb)
        if sim < min_similarity:
            continue
        scored.append((sim, item))

    scored.sort(key=lambda x: -x[0])
    scored = scored[:limit]

    results = []
    for sim, item in scored:
        results.append({
            "kind": item.source_type,
            "id": item.source_id,
            "title": item.title,
            "snippet": (item.text or "")[:200].replace("\n", " "),
            "url": item.url or "",
            "similarity": round(float(sim), 4),
        })
    return results
