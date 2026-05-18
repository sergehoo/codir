"""Services smart notes — parsing, autosave, publication.

Parsing
-------
On accepte deux formes en entrée :
  1. `content_json` : doc ProseMirror (Tiptap). On parcourt les blocs/paragraphes
     pour extraire les lignes commençant par `# `, `* `, `- `, etc.
  2. `content_md` : fallback texte plat (lignes séparées par `\\n`).

Règles de détection :
  - Une ligne préfixée `# ` → DÉCISION (titre = reste de la ligne).
  - Une ligne préfixée `* ` ou `- ` (avec indentation) → ACTION rattachée à la
    dernière décision détectée. Si pas de décision en cours, l'action est
    enregistrée mais non liée.
  - À l'intérieur d'une ligne d'action, `@Prénom Nom` → résolution best-effort
    sur le User actif. Si non résolu, on conserve le texte brut dans
    `assignee_mention`.

Publication
-----------
Materialize transforme les détectées en vrais objets métiers :
  - `MeetingDetectedDecision` → `apps.decisions.models.Decision`
  - `MeetingDetectedAction` → `apps.action_plans.models.ActionPlan + ActionTask`
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.action_plans.models import ActionPlan, ActionTask
from apps.common.enums import (
    ActionPlanStatus, ActionTaskStatus,
    DecisionStatus, ImpactLevel, Priority,
)
from apps.decisions.models import Decision

from .models import (
    DetectedDecisionStatus, Meeting, MeetingDetectedAction,
    MeetingDetectedDecision, MeetingMention, MeetingNote,
)

User = get_user_model()


# ─── Tiptap → texte plat ──────────────────────────────────────

def tiptap_to_lines(doc: dict) -> list[str]:
    """Convertit un document ProseMirror en liste de lignes texte.

    Reconnaît : paragraph, heading, listItem, bulletList, orderedList, codeBlock.
    Préserve les indentations imbriquées via 4 espaces par niveau.
    """
    if not isinstance(doc, dict):
        return []
    lines: list[str] = []

    def _walk(node, depth=0, in_bullet=False):
        if not isinstance(node, dict):
            return
        ntype = node.get("type")
        children = node.get("content", [])

        if ntype in ("paragraph", "heading"):
            text = _text_of(node)
            if in_bullet:
                lines.append("    " * depth + "* " + text)
            else:
                lines.append("    " * depth + text)
            return

        if ntype in ("bulletList", "orderedList"):
            for c in children:
                _walk(c, depth, in_bullet=True)
            return

        if ntype == "listItem":
            # Le 1er enfant est généralement un paragraph
            for c in children:
                _walk(c, depth + (1 if in_bullet else 0), in_bullet=True)
            return

        if ntype == "doc":
            for c in children:
                _walk(c, 0, False)
            return

        # fallback : descendre dans le contenu
        for c in children:
            _walk(c, depth, in_bullet)

    _walk(doc)
    return lines


def _text_of(node: dict) -> str:
    """Renvoie le texte concaténé d'un nœud ProseMirror."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = []
    for c in node.get("content", []) or []:
        parts.append(_text_of(c))
    return "".join(parts)


# ─── Parser ────────────────────────────────────────────────────

LINE_DECISION_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
# Actions et Tâches partagent la même cible (ActionTask).
# `*` ou `-` : item rapide (action mentionnée en séance).
# `>`        : tâche structurée (préfixe explicite alternatif).
LINE_ACTION_RE   = re.compile(r"^(\s*)[\*\->]\s+(.+?)\s*$")
MENTION_RE       = re.compile(r"@([A-Za-zÀ-ÿ\-']+(?:\s+[A-Za-zÀ-ÿ\-']+)*)")

# Date d'échéance inline : 22/08/2026 — 22/08/26 — 22/08
DUE_DATE_RE      = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

# Priorité inline : !low / !medium / !high / !critical (+ alias !l !m !h !c)
PRIORITY_RE      = re.compile(r"!(low|medium|high|critical|l|m|h|c)\b", re.IGNORECASE)
PRIORITY_ALIASES = {
    "l": "low", "m": "medium", "h": "high", "c": "critical",
    "low": "low", "medium": "medium", "high": "high", "critical": "critical",
}


def _extract_due_date(text: str, *, today=None):
    """Extrait une date DD/MM[/YY[YY]] du texte. Retourne (date|None, text_sans_date)."""
    from datetime import date as _date
    today = today or _date.today()
    m = DUE_DATE_RE.search(text)
    if not m:
        return None, text
    day, month = int(m.group(1)), int(m.group(2))
    year_raw = m.group(3)
    if year_raw is None:
        year = today.year
    else:
        year = int(year_raw)
        if year < 100:
            year += 2000
    try:
        dt = _date(year, month, day)
    except ValueError:
        return None, text  # ex: 31/02/2026 — non valide → on ignore
    cleaned = (text[: m.start()] + text[m.end():]).strip()
    return dt, re.sub(r"\s{2,}", " ", cleaned)


def _extract_priority(text: str):
    """Extrait une priorité !low|!medium|!high|!critical du texte."""
    m = PRIORITY_RE.search(text)
    if not m:
        return "", text
    raw = m.group(1).lower()
    priority = PRIORITY_ALIASES.get(raw, "")
    cleaned = (text[: m.start()] + text[m.end():]).strip()
    return priority, re.sub(r"\s{2,}", " ", cleaned)


@dataclass
class ParsedAction:
    title: str
    raw_line: str
    assignee: object = None  # User or None
    assignee_mention: str = ""
    order: int = 0
    due_date: object = None  # date | None
    priority: str = ""
    description_md: str = ""


@dataclass
class ParsedDecision:
    title: str
    raw_line: str
    order: int = 0
    actions: list[ParsedAction] = field(default_factory=list)


@dataclass
class ParseResult:
    decisions: list[ParsedDecision] = field(default_factory=list)
    orphan_actions: list[ParsedAction] = field(default_factory=list)
    mentions: dict[str, object] = field(default_factory=dict)  # raw_name → User or None

    def as_dict(self):
        def _action_dict(a):
            return {
                "title": a.title,
                "raw_line": a.raw_line,
                "assignee_id": str(a.assignee.id) if a.assignee else None,
                "assignee_name": (a.assignee.get_full_name() if a.assignee else None),
                "assignee_mention": a.assignee_mention,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "priority": a.priority or "",
                "description_md": a.description_md or "",
            }
        return {
            "decisions": [
                {
                    "title": d.title,
                    "raw_line": d.raw_line,
                    "order": d.order,
                    "actions": [_action_dict(a) for a in d.actions],
                }
                for d in self.decisions
            ],
            "orphan_actions": [_action_dict(a) for a in self.orphan_actions],
            "mentions": [
                {
                    "raw_text": k,
                    "user_id": str(v.id) if v else None,
                    "user_name": v.get_full_name() if v else None,
                }
                for k, v in self.mentions.items()
            ],
        }


def _resolve_user(name: str, candidates: Iterable) -> object | None:
    """Résout best-effort un texte de mention vers un User parmi candidates.

    Strategy : match exact full_name (insensible casse/accents), puis match sur prénom uniquement,
    puis fallback : retourne None.
    """
    needle = _normalize(name)
    for u in candidates:
        full = _normalize(u.get_full_name() or "")
        if full == needle:
            return u
    # Match prénom uniquement
    first = needle.split()[0] if needle else ""
    if first:
        for u in candidates:
            if _normalize(u.first_name) == first:
                return u
    return None


def _normalize(s: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower().strip())
        if unicodedata.category(c) != "Mn"
    )


def parse_notes(*, content_json: dict | None = None, content_md: str = "",
                organization=None) -> ParseResult:
    """Parse un document de notes et extrait les structures CODIR."""
    if content_json:
        lines = tiptap_to_lines(content_json)
    else:
        lines = (content_md or "").splitlines()

    # Resolve candidates
    candidates = []
    if organization is not None:
        candidates = list(User.objects.filter(
            memberships__organization=organization, is_active=True,
        ).distinct())

    result = ParseResult()
    current_decision: ParsedDecision | None = None
    current_action: ParsedAction | None = None  # pour capturer les desc indentées
    decision_order = 0
    action_order = 0

    def _flush_current_action():
        """Nettoie la description multi-ligne en cours."""
        nonlocal current_action
        if current_action and current_action.description_md:
            current_action.description_md = current_action.description_md.strip()
        current_action = None

    for raw in lines:
        if not raw.strip():
            _flush_current_action()
            continue

        # DECISION ?
        m = LINE_DECISION_RE.match(raw)
        if m:
            _flush_current_action()
            decision_order += 1
            current_decision = ParsedDecision(
                title=m.group(1).strip()[:400],
                raw_line=raw,
                order=decision_order,
            )
            result.decisions.append(current_decision)
            continue

        # ACTION ?
        m = LINE_ACTION_RE.match(raw)
        if m:
            _flush_current_action()
            action_order += 1
            text = m.group(2).strip()

            # Extraction date + priorité (avant les mentions pour ne pas
            # collisioner les regex, notamment !c qui pourrait être en bord
            # de mot).
            due_date, text = _extract_due_date(text)
            priority, text = _extract_priority(text)

            # Mentions
            assignee = None
            mention_raw = ""
            mention_match = MENTION_RE.search(text)
            if mention_match:
                mention_raw = mention_match.group(1).strip()
                assignee = _resolve_user(mention_raw, candidates)
                result.mentions[mention_raw] = assignee
                text = MENTION_RE.sub("", text).strip()

            # Nettoyage final : virer les éventuels mots de liaison "d'ici le"
            # / "avant le" laissés derrière par la suppression de la date.
            text = re.sub(
                r"\b(d'ici|avant|jusqu'au|le|pour)\s*(le)?\s*$",
                "", text, flags=re.IGNORECASE,
            ).strip()
            text = re.sub(r"\s{2,}", " ", text).strip()

            current_action = ParsedAction(
                title=text[:400],
                raw_line=raw,
                assignee=assignee,
                assignee_mention=mention_raw,
                order=action_order,
                due_date=due_date,
                priority=priority,
            )
            if current_decision:
                current_decision.actions.append(current_action)
            else:
                result.orphan_actions.append(current_action)
            continue

        # Ligne indentée (≥2 espaces ou tab) après une action → description
        if current_action and (raw.startswith("  ") or raw.startswith("\t")):
            indent_stripped = raw.lstrip(" \t").rstrip()
            if indent_stripped:
                if current_action.description_md:
                    current_action.description_md += "\n" + indent_stripped
                else:
                    current_action.description_md = indent_stripped
                continue

        # Ligne non-indentée : on clôt la capture de description en cours
        _flush_current_action()

        # Mentions hors action (paragraphe libre)
        for match in MENTION_RE.finditer(raw):
            mention_raw = match.group(1).strip()
            if mention_raw not in result.mentions:
                result.mentions[mention_raw] = _resolve_user(mention_raw, candidates)

    _flush_current_action()
    return result


# ─── Autosave ─────────────────────────────────────────────────

@transaction.atomic
def autosave_notes(*, meeting: Meeting, author, content_json: dict, content_md: str = "",
                   create_new_version: bool = False) -> MeetingNote:
    """Met à jour la note courante (in-place) ou crée une nouvelle version."""
    note = MeetingNote.unscoped.filter(meeting=meeting, is_current=True).first()
    if note is None:
        note = MeetingNote.unscoped.create(
            organization=meeting.organization, meeting=meeting,
            author=author, content_json=content_json or {},
            content_md=content_md or "",
            is_current=True, version=1,
            last_autosaved_at=timezone.now(),
        )
    elif create_new_version:
        # Snapshot l'ancienne et crée une nouvelle
        MeetingNote.unscoped.filter(meeting=meeting, is_current=True).update(is_current=False)
        note = MeetingNote.unscoped.create(
            organization=meeting.organization, meeting=meeting,
            author=author, content_json=content_json or {},
            content_md=content_md or "",
            is_current=True, version=note.version + 1,
            last_autosaved_at=timezone.now(),
        )
    else:
        note.content_json = content_json or {}
        note.content_md = content_md or ""
        note.last_autosaved_at = timezone.now()
        note.save(update_fields=["content_json", "content_md", "last_autosaved_at", "updated_at"])
    return note


# ─── Synchronisation des détectées ────────────────────────────

def _norm_title(s: str) -> str:
    """Normalise pour comparer deux titres (casse + espaces + accents)."""
    import unicodedata
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFD", (s or "").lower())
            if unicodedata.category(c) != "Mn"
        ).split()
    )


@transaction.atomic
def sync_detected_entities(*, meeting: Meeting, note: MeetingNote | None = None) -> dict:
    """Re-parse la note courante et synchronise les Detected* tables.

    Garde les Detected* `published` ou `dismissed` (ne PAS les recréer).
    Les `pending` sont remplacés par le nouveau parse.
    Dedup : si une ligne `# X` correspond à un titre déjà publié/rejeté
    sur la même réunion, on ne crée PAS de nouvelle détection pour elle.
    """
    note = note or MeetingNote.unscoped.filter(meeting=meeting, is_current=True).first()
    if not note:
        return {"decisions": 0, "actions": 0}

    parsed = parse_notes(
        content_json=note.content_json,
        content_md=note.content_md,
        organization=meeting.organization,
    )

    # Index des titres déjà traités (publish ou dismiss) pour cette réunion
    existing_decisions = MeetingDetectedDecision.unscoped.filter(
        meeting=meeting,
    ).exclude(status=DetectedDecisionStatus.PENDING)
    existing_dec_titles = {_norm_title(d.title): d for d in existing_decisions}

    existing_actions = MeetingDetectedAction.unscoped.filter(
        meeting=meeting,
    ).exclude(status=DetectedDecisionStatus.PENDING)
    # clé : (decision_id ou None, normalized title)
    existing_act_keys = {
        (str(a.detected_decision_id or ""), _norm_title(a.title)): a
        for a in existing_actions
    }

    # Purge uniquement les pending
    MeetingDetectedDecision.unscoped.filter(
        meeting=meeting, status=DetectedDecisionStatus.PENDING,
    ).delete()
    MeetingDetectedAction.unscoped.filter(
        meeting=meeting, status=DetectedDecisionStatus.PENDING,
        detected_decision__isnull=True,
    ).delete()

    # Recrée avec dedup
    dec_count = 0
    act_count = 0
    skipped_dec = 0
    skipped_act = 0

    for pd in parsed.decisions:
        key = _norm_title(pd.title)
        if key in existing_dec_titles:
            # Déjà publié ou rejeté → on s'attache à l'existant pour rattacher les actions
            dd = existing_dec_titles[key]
            skipped_dec += 1
        else:
            dd = MeetingDetectedDecision.unscoped.create(
                organization=meeting.organization, meeting=meeting, note=note,
                title=pd.title, raw_line=pd.raw_line, order=pd.order,
                status=DetectedDecisionStatus.PENDING,
            )
            dec_count += 1

        for pa in pd.actions:
            act_key = (str(dd.id), _norm_title(pa.title))
            if act_key in existing_act_keys:
                skipped_act += 1
                continue
            MeetingDetectedAction.unscoped.create(
                organization=meeting.organization, meeting=meeting,
                detected_decision=dd, title=pa.title, raw_line=pa.raw_line,
                assignee=pa.assignee, assignee_mention=pa.assignee_mention,
                order=pa.order, status=DetectedDecisionStatus.PENDING,
                due_date=pa.due_date, priority=pa.priority,
                description_md=pa.description_md,
            )
            act_count += 1

    for pa in parsed.orphan_actions:
        act_key = ("", _norm_title(pa.title))
        if act_key in existing_act_keys:
            skipped_act += 1
            continue
        MeetingDetectedAction.unscoped.create(
            organization=meeting.organization, meeting=meeting,
            detected_decision=None, title=pa.title, raw_line=pa.raw_line,
            assignee=pa.assignee, assignee_mention=pa.assignee_mention,
            order=pa.order, status=DetectedDecisionStatus.PENDING,
            due_date=pa.due_date, priority=pa.priority,
            description_md=pa.description_md,
        )
        act_count += 1

    # Mentions — toujours refresh complet
    MeetingMention.unscoped.filter(meeting=meeting).delete()
    for raw_text, user in parsed.mentions.items():
        MeetingMention.unscoped.create(
            organization=meeting.organization, meeting=meeting,
            raw_text=raw_text, user=user, occurrences=1,
        )

    return {
        "decisions": dec_count, "actions": act_count,
        "skipped_decisions": skipped_dec, "skipped_actions": skipped_act,
    }


# ─── Publication / matérialisation ────────────────────────────

@transaction.atomic
def publish_detected_decision(*, detected: MeetingDetectedDecision, by_user) -> Decision:
    """Crée une vraie Decision à partir d'une détection.

    Idempotent : si une Decision existe déjà sur la même réunion avec un
    titre normalisé identique, on la réutilise au lieu de créer un doublon.
    """
    if detected.status == DetectedDecisionStatus.PUBLISHED and detected.decision_id:
        return detected.decision

    # Dedup : cherche une Decision existante sur la même réunion avec même titre
    needle = _norm_title(detected.title)
    existing = None
    for d in Decision.unscoped.filter(
        organization=detected.meeting.organization,
        meeting=detected.meeting,
    ).only("id", "title", "ref"):
        if _norm_title(d.title) == needle:
            existing = d
            break

    if existing is not None:
        d = existing
    else:
        last_ref = Decision.unscoped.filter(
            organization=detected.meeting.organization,
            ref__startswith="DEC-",
        ).order_by("-ref").values_list("ref", flat=True).first()
        next_num = 1
        if last_ref:
            try:
                next_num = int(last_ref.split("-")[-1]) + 1
            except Exception:  # noqa: BLE001
                pass
        ref = f"DEC-{timezone.now().year}-{next_num:04d}"

        d = Decision.unscoped.create(
            organization=detected.meeting.organization,
            ref=ref,
            title=detected.title,
            meeting=detected.meeting,
            priority=Priority.HIGH,
            impact=ImpactLevel.MEDIUM,
            status=DecisionStatus.APPROVED,
            approved_at=timezone.now(),
            approved_by=by_user,
            created_by=by_user,
        )

    detected.decision = d
    detected.status = DetectedDecisionStatus.PUBLISHED
    detected.published_at = timezone.now()
    detected.published_by = by_user
    detected.save(update_fields=["decision", "status", "published_at", "published_by", "updated_at"])
    return d


@transaction.atomic
def publish_detected_action(*, detected: MeetingDetectedAction, by_user) -> ActionTask:
    """Crée un ActionPlan (si besoin) + ActionTask à partir d'une détection."""
    if detected.status == DetectedDecisionStatus.PUBLISHED and detected.action_task_id:
        return detected.action_task

    # Materialize la decision parente si elle ne l'est pas déjà
    decision = None
    plan = None
    if detected.detected_decision:
        dd = detected.detected_decision
        if not dd.decision_id:
            decision = publish_detected_decision(detected=dd, by_user=by_user)
        else:
            decision = dd.decision
        plan = ActionPlan.unscoped.filter(decision=decision).first()
        if not plan:
            plan = ActionPlan.unscoped.create(
                organization=detected.meeting.organization,
                decision=decision,
                title=f"Plan d'exécution — {decision.title}",
                owner=detected.assignee or by_user,
                status=ActionPlanStatus.OPEN,
            )

    if not plan:
        # Action orpheline → on crée un plan "Flash" sans décision liée :
        # on doit avoir une decision (ActionPlan.decision est obligatoire).
        # On crée donc une décision miroir.
        ref = f"DEC-{timezone.now().year}-FLASH-{detected.id.hex[:6].upper()}"
        decision = Decision.unscoped.create(
            organization=detected.meeting.organization,
            ref=ref, title=detected.title[:200],
            meeting=detected.meeting,
            priority=Priority.MEDIUM, impact=ImpactLevel.MEDIUM,
            status=DecisionStatus.APPROVED,
            approved_at=timezone.now(), approved_by=by_user,
            created_by=by_user,
        )
        plan = ActionPlan.unscoped.create(
            organization=detected.meeting.organization,
            decision=decision,
            title=f"Plan flash — {decision.title}",
            owner=detected.assignee or by_user,
            status=ActionPlanStatus.OPEN,
        )

    # Dedup task : si une ActionTask existe déjà dans le même plan avec
    # un titre normalisé identique, on la réutilise.
    needle = _norm_title(detected.title)
    task = None
    if plan:
        for t in ActionTask.unscoped.filter(action_plan=plan).only("id", "title"):
            if _norm_title(t.title) == needle:
                task = t
                break
    if task is None:
        # Priorité : prefer la valeur détectée si présente, sinon MEDIUM
        detected_prio = (detected.priority or "").lower()
        priority_value = detected_prio if detected_prio in {
            Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL,
        } else Priority.MEDIUM
        task = ActionTask.unscoped.create(
            organization=detected.meeting.organization,
            action_plan=plan,
            title=detected.title,
            description_md=detected.description_md or "",
            priority=priority_value,
            status=ActionTaskStatus.TODO,
            assignee=detected.assignee,
            due_date=detected.due_date,
        )

    detected.action_task = task
    detected.status = DetectedDecisionStatus.PUBLISHED
    detected.published_at = timezone.now()
    detected.published_by = by_user
    detected.save(update_fields=["action_task", "status", "published_at", "published_by", "updated_at"])
    return task


@transaction.atomic
def publish_all_pending(*, meeting: Meeting, by_user) -> dict:
    """Matérialise toutes les détections pending d'une réunion."""
    decisions = 0
    actions = 0
    for dd in MeetingDetectedDecision.unscoped.filter(
        meeting=meeting, status=DetectedDecisionStatus.PENDING,
    ):
        publish_detected_decision(detected=dd, by_user=by_user)
        decisions += 1
    for da in MeetingDetectedAction.unscoped.filter(
        meeting=meeting, status=DetectedDecisionStatus.PENDING,
    ):
        publish_detected_action(detected=da, by_user=by_user)
        actions += 1
    return {"decisions": decisions, "actions": actions}
