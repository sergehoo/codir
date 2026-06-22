"""Management command : (re)indexe tous les objets métier dans SemanticIndex.

Usage :
    python manage.py reindex_semantic                # tout
    python manage.py reindex_semantic --kinds decision plan
    python manage.py reindex_semantic --org <slug>   # limiter à une org
    python manage.py reindex_semantic --force        # ré-indexe même si hash inchangé

À lancer :
  - Après installation initiale du Lot 3.
  - Après upgrade du modèle d'embedding (change MODEL_VERSION_TAG).
  - Si l'index sémantique devient incohérent (rare, debug).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Bootstrap / rebuild de l'index sémantique pour la recherche IA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kinds", nargs="+",
            choices=["decision", "plan", "meeting", "transcript", "document"],
            default=None,
            help="Limiter aux types spécifiés (default: tous).",
        )
        parser.add_argument("--org", default=None, help="Slug de l'org à indexer (default: toutes).")
        parser.add_argument("--force", action="store_true",
                            help="Re-calcule même si text_hash inchangé.")

    def handle(self, *args, **opts):
        from apps.ai_engine.indexing import index_object
        from apps.ai_engine.models import SemanticIndex
        from apps.organizations.models import Organization

        kinds = opts.get("kinds") or ["decision", "plan", "meeting", "transcript"]
        org_slug = opts.get("org")
        force = opts.get("force", False)

        # Cible org(s)
        orgs = Organization.objects.filter(is_active=True)
        if org_slug:
            orgs = orgs.filter(slug=org_slug)
        if not orgs.exists():
            self.stdout.write(self.style.WARNING("Aucune org cible. Abort."))
            return

        total = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "error": 0}

        for org in orgs:
            self.stdout.write(self.style.NOTICE(f"\n● Org : {org.name} ({org.slug})"))
            for kind in kinds:
                count = self._reindex_kind(kind, org, force, total)
                self.stdout.write(f"   {kind:11} → {count} traité(s)")

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Terminé. created={total['created']} updated={total['updated']} "
            f"unchanged={total['unchanged']} skipped={total['skipped']} error={total['error']}"
        ))

    def _reindex_kind(self, kind: str, org, force: bool, total: dict) -> int:
        """Itère sur les objets d'un type et indexe chacun."""
        from apps.ai_engine.indexing import index_object
        from apps.ai_engine.models import SemanticIndex

        objects = self._fetch_objects(kind, org)
        if objects is None:
            return 0

        if force:
            # Invalide le hash existant pour forcer la ré-indexation
            SemanticIndex.unscoped.filter(
                organization=org, source_type=kind,
            ).update(text_hash="")

        count = 0
        for obj in objects:
            status = index_object(obj=obj, source_type=kind, organization=org)
            total[status] = total.get(status, 0) + 1
            count += 1
        return count

    def _fetch_objects(self, kind: str, org):
        """Retourne le queryset des objets du type donné pour l'org."""
        try:
            if kind == "decision":
                from apps.decisions.models import Decision
                return Decision.unscoped.filter(organization=org)
            if kind == "plan":
                from apps.action_plans.models import ActionPlan
                return ActionPlan.unscoped.filter(organization=org)
            if kind == "meeting":
                from apps.meetings.models import Meeting
                return Meeting.unscoped.filter(organization=org)
            if kind == "transcript":
                from apps.meeting_recordings.models import MeetingRecording
                return MeetingRecording.unscoped.filter(organization=org)
        except ImportError:
            return None
        return None
