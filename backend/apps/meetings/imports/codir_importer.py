"""
Importer CODIR — convertit le dict canonique extrait par ``codir_pdf_extractor``
en entités Django Meeting / Participant / Decision + ActionPlan + Task.

Stratégie :
  - Idempotent : utilise ``reference`` comme clé unique. Re-importer le même PDF
    ne crée jamais de doublon.
  - Matching User : nom complet → fuzzy match (rapidfuzz) avec seuil 85.
  - Matching Subsidiary : table de slugs fixes (alias Kaydan connus).
  - Matching Direction : par nom (organisation + subsidiary).
  - Une Action du PDF = une Decision (catégorie "Action CODIR") +
    un ActionPlan + autant d'ActionTask que de responsables.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone
from rapidfuzz import fuzz, process

from apps.accounts.models import User
from apps.action_plans.models import ActionPlan, ActionTask
from apps.common.enums import (
    ActionPlanStatus, ActionTaskStatus, AttendanceStatus,
    DecisionStatus, MeetingStatus, ParticipantRole, Priority,
)
from apps.decisions.models import Decision, DecisionCategory
from apps.governance.models import Direction
from apps.meetings.models import (
    Meeting, MeetingAttendance, MeetingParticipant, MeetingType,
)
from apps.organizations.models import Organization, Subsidiary

logger = logging.getLogger(__name__)


# ─── Mapping libellés CODIR vers slugs internes ─────────────────────────

# Entité (entity) du participant → slug à chercher dans Subsidiary.name
_SUBSIDIARY_ALIASES: dict[str, list[str]] = {
    "kaydan-groupe": ["KAYDAN GROUPE", "KAYDAN Groupe", "Kaydan Groupe"],
    "kaydan-re":     ["KAYDAN RE", "KAYDAN Real Estate", "Kaydan Real Estate", "KAYDAN R.E."],
    "kaydan-am":     ["KAYDAN Asset Management", "KAM"],
    "datarium":      ["DATARIUM", "Datarium"],
    "caffim":        ["CAFFIM Properties", "CAFFIM", "Caffim Properties"],
}

# Direction du tableau d'actions → nom canonique (utilisé pour Direction.name)
_DIRECTION_ALIASES: dict[str, list[str]] = {
    "DAF":              ["Direction administrative et financière"],
    "Supply Chain":     ["Direction Supply Chain et achats groupe", "Supply Chain", "DSCA"],
    "KAM":              ["KAYDAN Asset Management"],
    "Capital Humain":   ["Direction du capital humain", "DCH", "DRH"],
    "DATARIUM":         ["DATARIUM"],
    "DVRC":             ["Direction des ventes et de la relation client", "Ventes"],
    "Technique":        ["Direction technique", "DT"],
    "Stratégie Inv.":   ["Direction Stratégie et Investissements Immobiliers", "DSII", "Stratégie & Inv."],
    "CAFFIM":           ["CAFFIM Properties"],
}

# Status PDF → ActionTaskStatus
_TASK_STATUS_MAP = {
    "Non démarré": ActionTaskStatus.TODO,
    "En cours":    ActionTaskStatus.IN_PROGRESS,
    "En attente":  ActionTaskStatus.BLOCKED,
    "En retard":   ActionTaskStatus.OVERDUE,
    "Terminé":     ActionTaskStatus.DONE,
}

# Status PDF → DecisionStatus
_DECISION_STATUS_MAP = {
    "Non démarré": DecisionStatus.APPROVED,    # validée mais pas démarrée
    "En cours":    DecisionStatus.IN_PROGRESS,
    "En attente":  DecisionStatus.APPROVED,
    "En retard":   DecisionStatus.IN_PROGRESS,
    "Terminé":     DecisionStatus.COMPLETED,
}


# ─── Résultat de l'import ───────────────────────────────────────────────

@dataclass
class ImportReport:
    meeting_id: str | None = None
    meeting_created: bool = False
    participants_created: int = 0
    participants_matched: int = 0
    decisions_created: int = 0
    decisions_updated: int = 0
    tasks_created: int = 0
    tasks_updated: int = 0
    warnings: list[str] = field(default_factory=list)
    unmatched_assignees: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "meeting_created": self.meeting_created,
            "participants_created": self.participants_created,
            "participants_matched": self.participants_matched,
            "decisions_created": self.decisions_created,
            "decisions_updated": self.decisions_updated,
            "tasks_created": self.tasks_created,
            "tasks_updated": self.tasks_updated,
            "warnings": self.warnings,
            "unmatched_assignees": list(set(self.unmatched_assignees)),
        }


# ─── Helpers matching ───────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Normalise pour matching : lowercase, sans accents, sans espaces multiples."""
    import unicodedata
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())


def _match_subsidiary(label: str, org: Organization) -> Subsidiary | None:
    """Match Subsidiary par alias ou fuzzy match sur Subsidiary.name."""
    target = _normalize(label)
    # Recherche directe par alias
    for slug, aliases in _SUBSIDIARY_ALIASES.items():
        if any(_normalize(a) == target for a in aliases):
            sub = Subsidiary.objects.filter(
                organization=org, name__in=aliases,
            ).first()
            if sub:
                return sub
    # Fallback fuzzy
    subs = list(Subsidiary.objects.filter(organization=org))
    if not subs:
        return None
    names = {s.id: s.name for s in subs}
    best = process.extractOne(label, names, scorer=fuzz.WRatio, score_cutoff=80)
    if best:
        return next(s for s in subs if s.id == best[2])
    return None


def _match_direction(label: str, org: Organization) -> Direction | None:
    """Match Direction par nom (fuzzy) dans l'organisation."""
    if not label:
        return None
    dirs = list(Direction.objects.filter(organization=org))
    if not dirs:
        return None
    names = {d.id: d.name for d in dirs}
    best = process.extractOne(label, names, scorer=fuzz.WRatio, score_cutoff=80)
    if best:
        return next(d for d in dirs if d.id == best[2])
    return None


def _match_user(name: str, org: Organization, users_cache: dict | None = None) -> User | None:
    """Match User par nom complet (first_name + last_name) dans l'org."""
    if not name:
        return None
    # Cache pour éviter de re-query
    if users_cache is None or "qs" not in users_cache:
        if users_cache is None:
            users_cache = {}
        # User est lié à Organization via Membership (multi-tenant)
        users_cache["qs"] = list(
            User.objects.filter(
                memberships__organization=org,
                memberships__is_active=True,
            )
            .only("id", "first_name", "last_name", "email")
            .distinct()
        )
        users_cache["lookup"] = {
            u.id: f"{u.first_name} {u.last_name}".strip() or u.email
            for u in users_cache["qs"]
        }
    if not users_cache["qs"]:
        return None

    best = process.extractOne(
        name, users_cache["lookup"], scorer=fuzz.WRatio, score_cutoff=85,
    )
    if best:
        uid = best[2]
        return next(u for u in users_cache["qs"] if u.id == uid)
    return None


# ─── Catégorie + ref auto ───────────────────────────────────────────────

def _get_or_create_codir_category(org: Organization) -> DecisionCategory:
    cat, _ = DecisionCategory.objects.get_or_create(
        organization=org,
        name="Action CODIR",
        defaults={"color": "#ea580c", "description": "Action issue d'un relevé de CODIR"},
    )
    return cat


def _next_decision_ref(org: Organization, when: datetime) -> str:
    """Génère DEC-YYYY-NNNN avec compteur par organisation."""
    year = when.year
    last = (
        Decision.objects.filter(organization=org, ref__startswith=f"DEC-{year}-")
        .order_by("-ref")
        .values_list("ref", flat=True)
        .first()
    )
    if last:
        try:
            n = int(last.split("-")[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"DEC-{year}-{n:04d}"


# ─── API principale ─────────────────────────────────────────────────────

@transaction.atomic
def import_codir_data(
    data: dict[str, Any],
    organization: Organization,
    *,
    actor: User | None = None,
    dry_run: bool = False,
) -> ImportReport:
    """Crée ou met à jour Meeting + Participants + Decisions + ActionTasks
    depuis un dict extrait par ``codir_pdf_extractor.extract_codir_pdf()``.

    Si ``dry_run=True``, ne valide rien : on rollback et on retourne le rapport.
    """
    report = ImportReport()
    users_cache: dict = {}

    # ── 1. Meeting (upsert sur reference + organization) ──
    meeting_date = data["date"]
    if hasattr(meeting_date, "year"):
        scheduled_start = timezone.make_aware(
            datetime.combine(meeting_date, time(9, 0)), timezone.get_current_timezone()
        )
        scheduled_end = scheduled_start + timedelta(hours=3)
    else:
        scheduled_start = timezone.now()
        scheduled_end = scheduled_start + timedelta(hours=3)

    reference = data["reference"]
    title = data.get("title") or f"CODIR {meeting_date}"

    chair_user = _match_user(data.get("chair") or "", organization, users_cache)
    secretary_user = _match_user(data.get("rapporteur") or "", organization, users_cache)

    meeting, meeting_created = Meeting.objects.update_or_create(
        organization=organization,
        title=title,
        scheduled_start=scheduled_start,
        defaults={
            "description": f"Importé depuis {reference}",
            "meeting_type": MeetingType.STRATEGIC,
            "scheduled_end": scheduled_end,
            "actual_start": scheduled_start,
            "actual_end": scheduled_end,
            "status": MeetingStatus.COMPLETED,
            "chair": chair_user,
            "secretary": secretary_user,
            "final_notes_md": _build_summary_md(data),
            "created_by": actor,
            "quorum_reached": True,
        },
    )
    report.meeting_id = str(meeting.id)
    report.meeting_created = meeting_created

    # ── 2. Participants + attendances ──
    # Nettoie l'existant pour rester idempotent
    MeetingAttendance.objects.filter(meeting=meeting).delete()
    MeetingParticipant.objects.filter(meeting=meeting).delete()

    for p in data["participants"]:
        user = _match_user(p["name"], organization, users_cache)
        role = ParticipantRole.MEMBER
        if user and user == chair_user:
            role = ParticipantRole.CHAIR
        elif user and user == secretary_user:
            role = ParticipantRole.SECRETARY

        participant = MeetingParticipant.objects.create(
            organization=organization,
            meeting=meeting,
            user=user,
            external_name=p["name"] if user is None else "",
            external_email="" if user else None,
            role=role,
            is_required=True,
        )
        if user is None:
            report.warnings.append(f"Participant non matché : {p['name']} ({p['entity']})")
        else:
            report.participants_matched += 1
        report.participants_created += 1

        status = (
            AttendanceStatus.PRESENT if p["status"] == "present"
            else AttendanceStatus.ABSENT
        )
        MeetingAttendance.objects.create(
            organization=organization,
            meeting=meeting,
            participant=participant,
            status=status,
            recorded_by=actor,
        )

    # ── 3. Décisions + Action Plans + Tasks ──
    category = _get_or_create_codir_category(organization)

    for idx, a in enumerate(data["actions"], start=1):
        # Direction (governance) — best-effort
        direction = _match_direction(a["direction"], organization)

        # Title de la décision : "Direction — Projet"
        dec_title = f"{a['project']}".strip()[:300] or f"Action #{idx}"
        dec_status = _DECISION_STATUS_MAP.get(a["status"], DecisionStatus.APPROVED)

        # Idempotence : on identifie par (meeting, project) car le project est unique
        # dans un CODIR donné
        decision = Decision.objects.filter(
            organization=organization,
            meeting=meeting,
            title=dec_title,
        ).first()

        if decision:
            decision.description_md = a["action"]
            decision.status = dec_status
            decision.deadline = a["deadline"]
            decision.direction = direction
            decision.priority = (
                Priority.HIGH if a["status"] == "En retard" else Priority.MEDIUM
            )
            decision.save()
            report.decisions_updated += 1
        else:
            decision = Decision.objects.create(
                organization=organization,
                ref=_next_decision_ref(organization, scheduled_start),
                title=dec_title,
                description_md=a["action"],
                meeting=meeting,
                direction=direction,
                category=category,
                priority=(
                    Priority.HIGH if a["status"] == "En retard" else Priority.MEDIUM
                ),
                status=dec_status,
                deadline=a["deadline"],
                created_by=actor,
            )
            report.decisions_created += 1

        # ActionPlan associé (OneToOne avec Decision)
        plan, _ = ActionPlan.objects.update_or_create(
            decision=decision,
            defaults={
                "organization": organization,
                "title": dec_title[:300],
                "description_md": a["action"],
                "owner": _match_user(
                    a["assignees"][0] if a["assignees"] else "",
                    organization, users_cache,
                ),
                "target_end_date": a["deadline"],
                "status": _action_plan_status_from(a["status"]),
            },
        )

        # Une ActionTask par responsable (ou 1 sans assignee si vide)
        task_status = _TASK_STATUS_MAP.get(a["status"], ActionTaskStatus.TODO)
        task_assignees = a["assignees"] or [None]
        for assignee_name in task_assignees:
            assignee = (
                _match_user(assignee_name, organization, users_cache)
                if assignee_name else None
            )
            if assignee_name and not assignee:
                report.unmatched_assignees.append(assignee_name)

            task_title = a["action"][:300] if a["action"] else dec_title
            task, task_created = ActionTask.objects.update_or_create(
                action_plan=plan,
                title=task_title,
                assignee=assignee,
                defaults={
                    "organization": organization,
                    "description_md": (
                        f"{a['action']}\n\n_Commentaire CODIR :_ {a['comment']}"
                        if a["comment"] else a["action"]
                    ),
                    "priority": (
                        Priority.HIGH if a["status"] == "En retard" else Priority.MEDIUM
                    ),
                    "status": task_status,
                    "due_date": a["deadline"],
                },
            )
            if task_created:
                report.tasks_created += 1
            else:
                report.tasks_updated += 1

        # Recompute progress sur le plan
        plan.recompute_progress()
        plan.save(update_fields=["progress_percent"])

    if dry_run:
        # Forcer le rollback de toute la transaction
        transaction.set_rollback(True)

    return report


# ─── Helpers ────────────────────────────────────────────────────────────

def _action_plan_status_from(pdf_status: str) -> str:
    if pdf_status == "Terminé":
        return ActionPlanStatus.COMPLETED
    if pdf_status == "En attente":
        return ActionPlanStatus.BLOCKED
    if pdf_status == "En cours":
        return ActionPlanStatus.IN_PROGRESS
    return ActionPlanStatus.OPEN


def _build_summary_md(data: dict[str, Any]) -> str:
    """Génère un récap Markdown des notes finales (pour final_notes_md)."""
    lines = [
        f"# {data.get('title', 'CODIR')}",
        f"",
        f"**Référence** : {data['reference']}",
        f"**Date** : {data['date']}",
        f"**Présidence** : {data.get('chair') or '—'}",
        f"**Rapporteur** : {data.get('rapporteur') or '—'}",
        f"",
        f"## Ordre du jour",
    ]
    for item in data.get("agenda_items", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Participants ({len(data['participants'])})")
    for p in data["participants"]:
        marker = "✅" if p["status"] == "present" else "❌"
        lines.append(f"- {marker} **{p['name']}** — {p['role']} ({p['entity']})")
    return "\n".join(lines)
