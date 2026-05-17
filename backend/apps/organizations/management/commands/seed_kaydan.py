"""Seed initial — Kaydan Groupe + Filiales + Directions + 16 Users du CODIR.

Idempotent : peut être re-lancé sans créer de doublons.

Usage :
    python manage.py seed_kaydan [--password-default=Pwd2026!]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import Membership, Role, User
from apps.governance.models import Direction
from apps.organizations.models import Organization, Subsidiary


# ─── Données canoniques Kaydan ──────────────────────────────────────────

ORG_SLUG = "kaydan"
ORG_NAME = "Kaydan Groupe"

SUBSIDIARIES = [
    "KAYDAN Groupe",
    "KAYDAN RE",
    "KAYDAN Asset Management",
    "DATARIUM",
    "CAFFIM Properties",
]

# Directions opérationnelles du CODIR
DIRECTIONS = [
    ("Direction administrative et financière",            "DAF",      "KAYDAN RE"),
    ("Direction Supply Chain et achats groupe",           "DSCA",     "KAYDAN Groupe"),
    ("Direction du capital humain",                       "DCH",      "KAYDAN Groupe"),
    ("Direction des ventes et de la relation client",     "DVRC",     "KAYDAN RE"),
    ("Direction technique",                               "DT",       "KAYDAN RE"),
    ("Direction Stratégie et Investissements Immobiliers", "DSII",    "KAYDAN RE"),
    ("DATARIUM",                                          "DATARIUM", "DATARIUM"),
    ("KAYDAN Asset Management",                           "KAM",      "KAYDAN Asset Management"),
    ("CAFFIM Properties",                                 "CAFFIM",   "CAFFIM Properties"),
]

# Les 16 membres du CODIR KRE — emails canoniques @kaydan.com (à adapter)
USERS = [
    # nom complet, email, role/fonction, entité (subsidiary)
    ("Stéphane",        "AFFRO",        "stephane.affro@kaydan.com",       "Directeur Général",                                                "KAYDAN RE",                 True),
    ("Pierre-Michel",   "GOSSE",        "pierre-michel.gosse@kaydan.com",  "Directeur Général Adjoint",                                       "KAYDAN RE",                 True),
    ("Ette",            "KOUAKOU",      "ette.kouakou@kaydan.com",         "Directeur Administratif et Financier",                            "KAYDAN RE",                 True),
    ("Mariétou",        "COULIBALY",    "marietou.coulibaly@kaydan.com",   "Responsable Administratif et Financier",                          "KAYDAN RE",                 False),
    ("Omer",            "TANO",         "omer.tano@kaydan.com",            "Directeur des opérations techniques",                             "KAYDAN RE",                 True),
    ("Christian",       "YAO",          "christian.yao@kaydan.com",        "Responsable Administratif et Financier",                          "KAYDAN RE",                 False),
    ("Dominique",       "KOUYATE",      "dominique.kouyate@kaydan.com",    "Directeur Supply Chain & Achats Groupe",                          "KAYDAN Groupe",             True),
    ("Jean-Bernard",    "EPONOU",       "jean-bernard.eponou@kaydan.com",  "Directeur Général KAM",                                           "KAYDAN Asset Management",   True),
    ("Ekanza",          "BOSSON",       "ekanza.bosson@kaydan.com",        "Responsable CET",                                                 "KAYDAN RE",                 False),
    ("Arnaud",          "BOTI",         "arnaud.boti@datarium.com",        "Directeur Général DATARIUM",                                      "DATARIUM",                  True),
    ("Jean-Luc",        "SAMPAH",       "jean-luc.sampah@kaydan.com",      "Directeur des Ventes et de la Relation client",                   "KAYDAN RE",                 True),
    ("Rachel Youant",   "KOFFI",        "rachel.koffi@kaydan.com",         "Directrice du Capital Humain",                                    "KAYDAN Groupe",             True),
    ("Jhon",            "DJAMA",        "jhon.djama@kaydan.com",           "Chef de département promotion immobilière",                       "KAYDAN RE",                 False),
    ("Patrick",         "SORHO",        "patrick.sorho@kaydan.com",        "Chef de projet Programmes immobiliers",                           "KAYDAN RE",                 False),
    ("Constant",        "KOUASSI",      "constant.kouassi@kaydan.com",     "Directeur Technique",                                             "KAYDAN RE",                 True),
    ("Floriane",        "N'GUESSAN",    "floriane.nguessan@kaydan.com",    "Chef du bureau du Président, en charge du développement",         "KAYDAN RE",                 False),
]


class Command(BaseCommand):
    help = "Seed Kaydan Groupe : Organization + 5 Subsidiaries + 9 Directions + 16 Users CODIR."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password-default", default="Kaydan2026!",
            help="Password attribué à tous les users (à changer après 1er login).",
        )
        parser.add_argument(
            "--reset-passwords", action="store_true",
            help="Réinitialise le password de tous les users existants.",
        )

    def handle(self, *args, **opts):
        default_pwd = opts["password_default"]
        reset = opts["reset_passwords"]

        # ── 1. Organization ──
        org, created = Organization.unscoped.get_or_create(
            slug=ORG_SLUG,
            defaults={
                "name": ORG_NAME,
                "country": "CI",
                "timezone": "Africa/Abidjan",
                "currency": "XOF",
                "primary_color": "#ea580c",
                "secondary_color": "#1e293b",
            },
        )
        self._echo("Organization", org.name, created)

        # ── 2. Subsidiaries ──
        subs: dict[str, Subsidiary] = {}
        for name in SUBSIDIARIES:
            sub, c = Subsidiary.unscoped.get_or_create(
                organization=org, name=name,
                defaults={"country": "CI", "currency": "XOF"},
            )
            subs[name] = sub
            self._echo("  Subsidiary", name, c)

        # ── 3. Directions ──
        for name, code, sub_name in DIRECTIONS:
            d, c = Direction.unscoped.get_or_create(
                organization=org, name=name,
                defaults={"code": code, "subsidiary": subs.get(sub_name)},
            )
            self._echo("  Direction", f"{name} ({code})", c)

        # ── 4. Users + Memberships ──
        # Role "executive" pour les membres du COMEX
        exec_role, _ = Role.unscoped.get_or_create(
            organization=org, code="executive",
            defaults={"name": "Membre Comité de Direction"},
        )

        for first, last, email, fn, entity, is_executive in USERS:
            user, c = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "is_active": True,
                    "is_executive": is_executive,
                },
            )
            if c or reset:
                user.set_password(default_pwd)
                user.save()
            self._echo("    User", f"{first} {last} <{email}>", c)

            # Résolution de la filiale du user à partir du PDF
            user_subsidiary = subs.get(entity)

            # Membership (avec subsidiary)
            mem, mc = Membership.unscoped.get_or_create(
                organization=org, user=user,
                defaults={
                    "is_executive": is_executive,
                    "is_active": True,
                    "subsidiary": user_subsidiary,
                },
            )
            # Si Membership existe déjà mais sans subsidiary → on l'enrichit
            if not mc and mem.subsidiary_id is None and user_subsidiary:
                mem.subsidiary = user_subsidiary
                mem.save(update_fields=["subsidiary"])
                self._echo("    ↳ Filiale", f"{first} {last} → {user_subsidiary.name}", True)

            if mc and is_executive:
                mem.roles.add(exec_role)

        # ── Récap ──
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✓ Seed Kaydan terminé."))
        self.stdout.write(
            f"  Org={Organization.unscoped.filter(slug=ORG_SLUG).count()}, "
            f"Sub={Subsidiary.unscoped.filter(organization=org).count()}, "
            f"Dir={Direction.unscoped.filter(organization=org).count()}, "
            f"Users={User.objects.filter(memberships__organization=org).distinct().count()}"
        )
        self.stdout.write(self.style.WARNING(
            f"  Password par défaut : {default_pwd}  (à changer après 1er login !)"
        ))

    def _echo(self, kind: str, label: str, created: bool):
        marker = self.style.SUCCESS("+ ") if created else self.style.NOTICE("= ")
        self.stdout.write(f"{marker}{kind:14} {label}")
