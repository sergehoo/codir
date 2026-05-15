"""Commande management : importe un CR CODIR PDF dans la base.

Usage :
    python manage.py import_codir_pdf <pdf_path> --org <slug> [--dry-run] [--actor <email>]

Exemple :
    python manage.py import_codir_pdf /tmp/CR_CODIR_KRE_11052026.pdf --org kaydan --actor admin@kaydan.com

Le mode --dry-run rollback la transaction (rien n'est persisté) et affiche
le rapport. Idéal pour valider avant un import réel.
"""
from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.meetings.imports.codir_importer import import_codir_data
from apps.meetings.imports.codir_pdf_extractor import extract_codir_pdf
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Importe un CR CODIR PDF (Kaydan) dans la base CODIR."

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", help="Chemin vers le fichier PDF.")
        parser.add_argument(
            "--org", required=True,
            help="Slug de l'Organization cible (ex: kaydan).",
        )
        parser.add_argument(
            "--actor", default=None,
            help="Email du User qui sera enregistré comme créateur. Optionnel.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Ne persiste rien — rollback en fin et affiche le rapport.",
        )
        parser.add_argument(
            "--json", action="store_true",
            help="Sortie au format JSON (utile pour pipelines).",
        )
        parser.add_argument(
            "--extract-only", action="store_true",
            help="Affiche uniquement les données extraites, sans toucher à la DB.",
        )

    def handle(self, *args, **opts):
        pdf_path = opts["pdf_path"]
        org_slug = opts["org"]
        actor_email = opts["actor"]
        dry_run = opts["dry_run"]
        as_json = opts["json"]
        extract_only = opts["extract_only"]

        # 1. Extraction
        try:
            data = extract_codir_pdf(pdf_path)
        except FileNotFoundError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Erreur d'extraction : {e}")

        if extract_only:
            self.stdout.write(json.dumps(data, default=str, ensure_ascii=False, indent=2))
            return

        # 2. Résolution de l'organisation
        try:
            org = Organization.unscoped.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{org_slug}' introuvable.")

        actor = None
        if actor_email:
            try:
                actor = User.objects.get(email=actor_email)
            except User.DoesNotExist:
                raise CommandError(f"User actor '{actor_email}' introuvable.")

        # 3. Import
        report = import_codir_data(data, org, actor=actor, dry_run=dry_run)

        # 4. Rendu
        payload = {
            "pdf_path": pdf_path,
            "organization": org.slug,
            "dry_run": dry_run,
            "extraction": {
                "reference": data["reference"],
                "date": str(data["date"]),
                "title": data["title"],
                "chair": data["chair"],
                "rapporteur": data["rapporteur"],
                "participants_total": len(data["participants"]),
                "participants_present": sum(
                    1 for p in data["participants"] if p["status"] == "present"
                ),
                "participants_absent": sum(
                    1 for p in data["participants"] if p["status"] == "absent"
                ),
                "actions_total": len(data["actions"]),
            },
            "report": report.to_dict(),
        }

        if as_json:
            self.stdout.write(json.dumps(payload, default=str, ensure_ascii=False, indent=2))
            return

        # Sortie humaine
        self.stdout.write(self.style.SUCCESS(
            f"✓ {payload['extraction']['reference']} — {payload['extraction']['date']}"
        ))
        self.stdout.write(
            f"  Participants : {payload['extraction']['participants_total']} "
            f"({payload['extraction']['participants_present']} présents, "
            f"{payload['extraction']['participants_absent']} absents)"
        )
        self.stdout.write(f"  Actions extraites : {payload['extraction']['actions_total']}")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Rapport d'import :"))
        for k, v in report.to_dict().items():
            if isinstance(v, list):
                if v:
                    self.stdout.write(f"  {k} ({len(v)}) :")
                    for item in v[:10]:
                        self.stdout.write(f"    - {item}")
                    if len(v) > 10:
                        self.stdout.write(f"    … +{len(v) - 10} autres")
            else:
                self.stdout.write(f"  {k} : {v}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n--dry-run actif : aucune donnée n'a été persistée."
            ))
