"""Nettoie les doublons de décisions et tâches générés par l'éditeur smart-notes.

Usage :
    python manage.py dedupe_decisions
    python manage.py dedupe_decisions --dry-run
"""
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.action_plans.models import ActionPlan, ActionTask
from apps.decisions.models import Decision
from apps.meetings.models import (
    DetectedDecisionStatus, MeetingDetectedAction, MeetingDetectedDecision,
)


def norm(s: str) -> str:
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFD", (s or "").lower())
            if unicodedata.category(c) != "Mn"
        ).split()
    )


class Command(BaseCommand):
    help = "Dédoublonne les Decisions et ActionTasks créées par l'éditeur smart-notes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        report = {
            "decisions_merged": 0,
            "tasks_merged": 0,
            "detected_relinked": 0,
        }

        # ─── Étape 1 : merge des Decisions par (organization, meeting, normalized title)
        seen: dict[tuple, Decision] = {}
        with transaction.atomic():
            for d in Decision.unscoped.filter(meeting__isnull=False).order_by("created_at"):
                key = (d.organization_id, d.meeting_id, norm(d.title))
                canon = seen.get(key)
                if canon is None:
                    seen[key] = d
                    continue
                # d est un doublon → repointer ActionPlan + MeetingDetectedDecision vers canon, puis supprimer d
                msg = f"  · {d.ref} ({d.title!r}) → fusion avec {canon.ref}"
                self.stdout.write(msg)
                report["decisions_merged"] += 1
                if dry:
                    continue
                # ActionPlan ← decision (OneToOne sur certains schémas, ForeignKey)
                ActionPlan.unscoped.filter(decision=d).update(decision=canon)
                # MeetingDetectedDecision.decision = d → canon
                MeetingDetectedDecision.unscoped.filter(decision=d).update(decision=canon)
                d.delete()

        # ─── Étape 2 : merge des ActionTasks par (action_plan, normalized title)
        with transaction.atomic():
            seen_t: dict[tuple, ActionTask] = {}
            for t in ActionTask.unscoped.all().order_by("created_at"):
                key = (t.action_plan_id, norm(t.title))
                canon = seen_t.get(key)
                if canon is None:
                    seen_t[key] = t
                    continue
                msg = f"  · Tâche {t.title!r} ({t.id}) → fusion avec {canon.id}"
                self.stdout.write(msg)
                report["tasks_merged"] += 1
                if dry:
                    continue
                # Repointer les MeetingDetectedAction
                MeetingDetectedAction.unscoped.filter(action_task=t).update(action_task=canon)
                t.delete()

        # ─── Étape 3 : repointer les MeetingDetectedDecision pending dont une version publiée existe
        with transaction.atomic():
            for dd in MeetingDetectedDecision.unscoped.filter(
                status=DetectedDecisionStatus.PENDING,
            ).select_related("meeting"):
                # Cherche une publication équivalente
                existing = None
                for sibling in MeetingDetectedDecision.unscoped.filter(
                    meeting=dd.meeting,
                ).exclude(id=dd.id).exclude(status=DetectedDecisionStatus.PENDING):
                    if norm(sibling.title) == norm(dd.title):
                        existing = sibling
                        break
                if existing and not dry:
                    dd.delete()
                    report["detected_relinked"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nFusionnées : {report['decisions_merged']} décisions · "
            f"{report['tasks_merged']} tâches · "
            f"{report['detected_relinked']} détections nettoyées."
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(dry-run : aucune modification appliquée)"))
