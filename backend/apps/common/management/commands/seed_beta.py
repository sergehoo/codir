"""Management command : seed bêta CODIR — multi-filiales, riche, idempotent.

Usage :
    python manage.py seed_beta            # crée si absent
    python manage.py seed_beta --reset    # purge puis crée
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Membership, Role
from apps.action_plans.models import ActionComment, ActionPlan, ActionTask
from apps.agendas.models import Agenda, AgendaItem
from apps.audit_logs.models import AuditLog
from apps.common.enums import (
    ActionPlanStatus, ActionTaskStatus, AgendaItemStatus,
    AttendanceStatus, DecisionStatus, ImpactLevel, MeetingStatus,
    ParticipantRole, Priority,
)
from apps.decisions.models import Decision, DecisionCategory, DecisionComment, DecisionHistory
from apps.governance.models import Direction
from apps.meetings.models import (
    Meeting, MeetingAttendance, MeetingMinutes,
    MeetingParticipant, MeetingType,
)
from apps.notifications.models import Notification, NotificationEvent, NotificationLevel
from apps.organizations.models import Organization, Plan, Subsidiary
from core.managers.tenant import current_organization

User = get_user_model()

# Reproductibilité
random.seed(2026)

SUBSIDIARIES = [
    {"name": "Kaydan France",        "country": "FR", "currency": "EUR"},
    {"name": "Kaydan Côte d'Ivoire", "country": "CI", "currency": "XOF"},
    {"name": "Kaydan Maroc",         "country": "MA", "currency": "MAD"},
    {"name": "Kaydan Sénégal",       "country": "SN", "currency": "XOF"},
]

DIRECTIONS_BY_SUB = {
    "Kaydan France":        ["Direction Générale", "DAF", "DSI", "DRH", "Commercial"],
    "Kaydan Côte d'Ivoire": ["DG Locale", "DAF", "Opérations", "Commercial"],
    "Kaydan Maroc":         ["DG Locale", "DAF", "DSI"],
    "Kaydan Sénégal":       ["DG Locale", "Commercial", "Opérations"],
}

USERS = [
    # France — direction groupe
    {"email": "dg@acme.local",        "first": "Catherine", "last": "Martin",   "exec": True,  "sub": "Kaydan France",        "dir": "Direction Générale"},
    {"email": "daf@acme.local",       "first": "Pierre",    "last": "Martin",   "exec": True,  "sub": "Kaydan France",        "dir": "DAF"},
    {"email": "dsi@acme.local",       "first": "Léa",       "last": "Dupont",   "exec": True,  "sub": "Kaydan France",        "dir": "DSI"},
    {"email": "drh@acme.local",       "first": "Sophie",    "last": "Klein",    "exec": True,  "sub": "Kaydan France",        "dir": "DRH"},
    {"email": "sec@acme.local",       "first": "Marc",      "last": "Renaud",   "exec": False, "sub": "Kaydan France",        "dir": "Direction Générale"},
    {"email": "com.fr@acme.local",    "first": "Julien",    "last": "Mercier",  "exec": False, "sub": "Kaydan France",        "dir": "Commercial"},
    # CI
    {"email": "dg.ci@acme.local",     "first": "Aïssatou",  "last": "Diallo",   "exec": True,  "sub": "Kaydan Côte d'Ivoire", "dir": "DG Locale"},
    {"email": "daf.ci@acme.local",    "first": "Mamadou",   "last": "Touré",    "exec": True,  "sub": "Kaydan Côte d'Ivoire", "dir": "DAF"},
    {"email": "ops.ci@acme.local",    "first": "Fatou",     "last": "Koné",     "exec": False, "sub": "Kaydan Côte d'Ivoire", "dir": "Opérations"},
    {"email": "com.ci@acme.local",    "first": "Yves",      "last": "N'Guessan","exec": False, "sub": "Kaydan Côte d'Ivoire", "dir": "Commercial"},
    # MA
    {"email": "dg.ma@acme.local",     "first": "Karim",     "last": "Bennani",  "exec": True,  "sub": "Kaydan Maroc",         "dir": "DG Locale"},
    {"email": "daf.ma@acme.local",    "first": "Salima",    "last": "El Idrissi","exec": True, "sub": "Kaydan Maroc",         "dir": "DAF"},
    {"email": "dsi.ma@acme.local",    "first": "Younes",    "last": "Tazi",     "exec": False, "sub": "Kaydan Maroc",         "dir": "DSI"},
    # SN
    {"email": "dg.sn@acme.local",     "first": "Awa",       "last": "Sow",      "exec": True,  "sub": "Kaydan Sénégal",       "dir": "DG Locale"},
    {"email": "com.sn@acme.local",    "first": "Cheikh",    "last": "Ndiaye",   "exec": False, "sub": "Kaydan Sénégal",       "dir": "Commercial"},
    {"email": "ops.sn@acme.local",    "first": "Khady",     "last": "Faye",     "exec": False, "sub": "Kaydan Sénégal",       "dir": "Opérations"},
]

ROLES_DEF = [
    ("OWNER",     "Propriétaire"),
    ("CHAIRMAN",  "Président"),
    ("SECRETARY", "Secrétaire"),
    ("EXECUTIVE", "Exécutif"),
    ("MEMBER",    "Membre"),
]

DECISION_CATEGORIES = [
    {"name": "Investissement",   "color": "#B8693C"},
    {"name": "Stratégie",        "color": "#2563EB"},
    {"name": "Réorganisation",   "color": "#7C3AED"},
    {"name": "Opérationnel",     "color": "#0EA5E9"},
    {"name": "Conformité",       "color": "#EAB308"},
]

# Briques pour générer titres réalistes
MEETING_TITLES = [
    "Comité de direction hebdomadaire",
    "Revue stratégique trimestrielle",
    "CODIR de crise — situation cyber",
    "Comité financier mensuel",
    "Comité Innovation & SI",
    "Revue des projets en cours",
    "Comité RH et talents",
    "CODIR extraordinaire — acquisition",
    "Revue commerciale Q2",
    "Comité ESG / Conformité",
    "Préparation budget 2027",
    "Comité opérationnel Afrique",
]

DECISION_BRIEFS = [
    ("Lancement projet Phoenix",                   ImpactLevel.STRATEGIC, Priority.CRITICAL),
    ("Acquisition NovaTech — Lettre d'intention",  ImpactLevel.STRATEGIC, Priority.HIGH),
    ("Renouvellement du contrat cloud AWS",        ImpactLevel.HIGH,      Priority.HIGH),
    ("Politique de télétravail Groupe",            ImpactLevel.MEDIUM,    Priority.MEDIUM),
    ("Restructuration zone CEMAC",                 ImpactLevel.STRATEGIC, Priority.CRITICAL),
    ("Plan de continuité d'activité — refonte",    ImpactLevel.HIGH,      Priority.HIGH),
    ("Audit Cyber 2026 — sélection prestataire",   ImpactLevel.HIGH,      Priority.HIGH),
    ("Ouverture filiale Côte d'Ivoire phase 2",    ImpactLevel.STRATEGIC, Priority.HIGH),
    ("Stratégie ESG et reporting CSRD",            ImpactLevel.HIGH,      Priority.MEDIUM),
    ("Refonte SI commercial — choix CRM",          ImpactLevel.HIGH,      Priority.HIGH),
    ("Augmentation enveloppe formation 2026",      ImpactLevel.MEDIUM,    Priority.MEDIUM),
    ("Politique de signature électronique",        ImpactLevel.MEDIUM,    Priority.LOW),
    ("Externalisation paie filiale Maroc",         ImpactLevel.MEDIUM,    Priority.MEDIUM),
    ("Refinancement dette à long terme",           ImpactLevel.STRATEGIC, Priority.CRITICAL),
    ("Plan de réduction de la trésorerie négative",ImpactLevel.HIGH,      Priority.HIGH),
    ("Cession activité distribution Sénégal",      ImpactLevel.STRATEGIC, Priority.HIGH),
    ("Nouvelle politique de mobilité interne",     ImpactLevel.MEDIUM,    Priority.LOW),
    ("Renouvellement gouvernance Comex",           ImpactLevel.HIGH,      Priority.MEDIUM),
    ("Stratégie commerciale T3",                   ImpactLevel.HIGH,      Priority.HIGH),
    ("Migration ERP filiale Maroc",                ImpactLevel.HIGH,      Priority.HIGH),
]

TASK_TEMPLATES_BY_DECISION = {
    "Lancement projet Phoenix": [
        "Constituer l'équipe pluri-disciplinaire",
        "Cadrer le besoin métier et lock budget",
        "Choisir le prestataire d'intégration",
        "Lancer les ateliers utilisateurs",
        "Définir la roadmap T2-T3",
    ],
    "Acquisition NovaTech — Lettre d'intention": [
        "Due diligence financière",
        "Due diligence juridique",
        "Préparer la LOI",
        "Présentation Comex",
    ],
    "Renouvellement du contrat cloud AWS": [
        "Benchmark 3 fournisseurs cloud",
        "Négociation tarifs AWS Enterprise",
        "Validation conformité RGPD",
        "Signature contrat",
    ],
    "Restructuration zone CEMAC": [
        "État des lieux organisationnel",
        "Plan de communication interne",
        "Validation juridique des transferts",
    ],
    "Audit Cyber 2026 — sélection prestataire": [
        "Rédiger le cahier des charges",
        "Lancer l'appel d'offres",
        "Auditer 3 candidats finalistes",
        "Choisir et notifier le retenu",
    ],
    "Refonte SI commercial — choix CRM": [
        "Benchmark 5 solutions CRM",
        "POC sur 2 solutions",
        "Vote du Comex",
        "Préparer migration des données",
        "Plan de formation commerciaux",
    ],
    "Migration ERP filiale Maroc": [
        "Audit existant SAGE local",
        "Préparer plan de migration",
        "Test environnement de recette",
        "Migration production",
    ],
}

DEFAULT_TASKS = [
    "Préparer le dossier de présentation",
    "Valider auprès de la DAF",
    "Coordonner avec le juridique",
    "Faire approuver par le Comex",
    "Lancer la phase pilote",
    "Évaluer les retours utilisateurs",
    "Rédiger note de cadrage",
]

NOTIF_BODIES = [
    "Préparation de la prochaine session — penser à valider l'agenda.",
    "Échéance dans 72h — merci de finaliser votre contribution.",
    "Décision validée à l'unanimité — exécution démarrée.",
    "Quorum non atteint sur la séance du jour — replanification nécessaire.",
    "Document confidentiel partagé — accès restreint à 5 membres.",
]


class Command(BaseCommand):
    help = "Seed bêta CODIR — multi-filiales, plusieurs réunions, tâches réparties."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Purge avant seed")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self._reset()

        # 1) Organization tenant
        org, _ = Organization.unscoped.get_or_create(
            slug="acme", defaults={
                "name": "Acme Corp",
                "country": "FR", "timezone": "Europe/Paris",
                "currency": "EUR", "plan": Plan.ENTERPRISE,
            },
        )
        token = current_organization.set(org)
        try:
            self._seed(org)
        finally:
            current_organization.reset(token)

        self.stdout.write(self.style.SUCCESS(
            "✓ Seed bêta riche terminé — multi-filiales, plusieurs réunions, tâches réparties."
        ))

    def _reset(self):
        for m in (
            Notification, AuditLog,
            ActionComment, ActionTask, ActionPlan,
            DecisionComment, DecisionHistory, Decision, DecisionCategory,
            AgendaItem, Agenda,
            MeetingMinutes, MeetingAttendance, MeetingParticipant, Meeting,
            Direction, Subsidiary,
            Membership, Role, Organization,
        ):
            m.unscoped.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        self.stdout.write("Reset effectué.")

    def _seed(self, org: Organization):
        # ─── Subsidiaries ────────────────────────────────────
        subs = {}
        for s in SUBSIDIARIES:
            obj, _ = Subsidiary.unscoped.get_or_create(
                organization=org, name=s["name"],
                defaults={"country": s["country"], "currency": s["currency"]},
            )
            subs[s["name"]] = obj
        self.stdout.write(f"  • {len(subs)} filiales")

        # ─── Directions ──────────────────────────────────────
        directions = {}
        for sub_name, dir_list in DIRECTIONS_BY_SUB.items():
            sub = subs[sub_name]
            for dir_name in dir_list:
                key = (sub_name, dir_name)
                obj, _ = Direction.unscoped.get_or_create(
                    organization=org, subsidiary=sub, name=dir_name,
                )
                directions[key] = obj
        self.stdout.write(f"  • {len(directions)} directions")

        # ─── Roles ───────────────────────────────────────────
        roles = {}
        for code, name in ROLES_DEF:
            r, _ = Role.unscoped.get_or_create(
                organization=org, code=code,
                defaults={"name": name, "is_system": True},
            )
            roles[code] = r

        # ─── Users + Memberships ─────────────────────────────
        users = {}
        for u in USERS:
            user, created = User.objects.get_or_create(
                email=u["email"],
                defaults={
                    "first_name": u["first"], "last_name": u["last"],
                    "is_executive": u["exec"],
                },
            )
            if created:
                user.set_password("Codir!2026")
                user.save()
            users[u["email"]] = user

            membership, _ = Membership.unscoped.get_or_create(
                organization=org, user=user,
                defaults={
                    "is_owner": u["email"] == "dg@acme.local",
                    "is_executive": u["exec"], "is_active": True,
                },
            )
            # Direction
            d = directions.get((u["sub"], u["dir"]))
            if d:
                membership.directions.add(d)
            # Role
            role_code = "OWNER" if u["email"] == "dg@acme.local" else (
                "SECRETARY" if u["email"] == "sec@acme.local" else
                "EXECUTIVE" if u["exec"] else "MEMBER"
            )
            membership.roles.add(roles[role_code])
        self.stdout.write(f"  • {len(users)} utilisateurs avec memberships")

        # ─── Decision categories ─────────────────────────────
        cats = {}
        for c in DECISION_CATEGORIES:
            obj, _ = DecisionCategory.unscoped.get_or_create(
                organization=org, name=c["name"], defaults={"color": c["color"]},
            )
            cats[c["name"]] = obj

        # ─── Meetings ─────────────────────────────────────────
        now = timezone.now()
        # On crée 12 réunions avec dates variées : passées, en cours, à venir
        dg = users["dg@acme.local"]
        sec = users["sec@acme.local"]
        meetings: list[Meeting] = []
        for i, title in enumerate(MEETING_TITLES):
            # Distribution : 3 passées, 2 in_progress, 4 scheduled future, 2 cancelled, 1 draft
            if i < 3:
                start = now - timedelta(days=14 + i * 7)
                status = MeetingStatus.COMPLETED
            elif i < 5:
                start = now - timedelta(hours=1)
                status = MeetingStatus.IN_PROGRESS
            elif i < 9:
                start = now + timedelta(days=2 + (i - 5) * 4)
                status = MeetingStatus.SCHEDULED
            elif i < 11:
                start = now - timedelta(days=3 + i)
                status = MeetingStatus.CANCELLED
            else:
                start = now + timedelta(days=20)
                status = MeetingStatus.DRAFT

            end = start + timedelta(hours=2)
            m = Meeting.unscoped.create(
                organization=org,
                title=title,
                description=f"Session #{i + 1} — pilotage Groupe Kaydan",
                meeting_type=random.choice(list(MeetingType.values)),
                scheduled_start=start, scheduled_end=end,
                actual_start=start if status in (MeetingStatus.IN_PROGRESS, MeetingStatus.COMPLETED) else None,
                actual_end=end if status == MeetingStatus.COMPLETED else None,
                location=random.choice([
                    "Salle Conseil — Siège Paris", "Visio uniquement",
                    "Salle Comex — La Défense", "Bureaux Abidjan", "Salle Atlas — Casablanca",
                ]),
                video_url=random.choice(["https://teams.microsoft.com/l/codir", "", ""]),
                status=status,
                chair=dg, secretary=sec, quorum_min=4,
                quorum_reached=status == MeetingStatus.COMPLETED,
                created_by=dg,
            )
            # Participants — varie selon meeting
            participants = list(users.values())
            random.shuffle(participants)
            for u in participants[:random.randint(6, 12)]:
                MeetingParticipant.unscoped.get_or_create(
                    organization=org, meeting=m, user=u,
                    defaults={
                        "role": ParticipantRole.CHAIR if u == dg else
                                (ParticipantRole.SECRETARY if u == sec else ParticipantRole.MEMBER),
                    },
                )
            meetings.append(m)

            # Agenda + items pour les réunions non-draft
            if status != MeetingStatus.DRAFT:
                agenda = Agenda.unscoped.create(
                    organization=org, meeting=m,
                    is_validated=status != MeetingStatus.DRAFT,
                    validated_by=dg if status != MeetingStatus.DRAFT else None,
                    validated_at=now if status != MeetingStatus.DRAFT else None,
                )
                for j, t in enumerate([
                    "Approbation PV séance précédente",
                    "Point d'actualité financier",
                    f"Revue {title.lower()}",
                    "Décisions à acter",
                    "Tour de table",
                ]):
                    AgendaItem.unscoped.create(
                        organization=org, agenda=agenda, order=j + 1,
                        title=t,
                        priority=random.choice(list(Priority.values)),
                        estimated_duration_minutes=random.choice([10, 15, 20, 30]),
                        responsible=random.choice(list(users.values())),
                        status=(AgendaItemStatus.DISCUSSED if status == MeetingStatus.COMPLETED
                                else AgendaItemStatus.PENDING),
                    )

            # Présences pour réunions en cours / passées
            if status in (MeetingStatus.IN_PROGRESS, MeetingStatus.COMPLETED):
                for p in m.participants.all():
                    MeetingAttendance.unscoped.create(
                        organization=org, meeting=m, participant=p,
                        status=random.choice([
                            AttendanceStatus.PRESENT, AttendanceStatus.PRESENT,
                            AttendanceStatus.PRESENT, AttendanceStatus.LATE,
                            AttendanceStatus.ABSENT,
                        ]),
                    )
        self.stdout.write(f"  • {len(meetings)} réunions (passées, en cours, à venir)")

        # ─── Decisions ────────────────────────────────────────
        decisions: list[Decision] = []
        users_list = list(users.values())
        for i, (title, impact, priority) in enumerate(DECISION_BRIEFS):
            sub_name = random.choice(list(subs.keys()))
            dir_options = DIRECTIONS_BY_SUB[sub_name]
            dir_obj = directions[(sub_name, random.choice(dir_options))]
            # Status distribution
            r = random.random()
            if r < 0.15:    status = DecisionStatus.PROPOSED
            elif r < 0.35:  status = DecisionStatus.APPROVED
            elif r < 0.60:  status = DecisionStatus.IN_PROGRESS
            elif r < 0.78:  status = DecisionStatus.COMPLETED
            elif r < 0.88:  status = DecisionStatus.POSTPONED
            else:           status = DecisionStatus.CANCELLED

            def _user_in_direction(u, target_dir):
                m = Membership.unscoped.filter(user=u, organization=org).first()
                if not m or not target_dir:
                    return False
                return target_dir in m.directions.all()

            responsible = next(
                (u for u in users_list if _user_in_direction(u, dir_obj)),
                random.choice(users_list),
            )

            # Échéance — parfois passée (retard)
            offset = random.choice([-15, -5, 7, 14, 30, 45, 60, 90])
            ref = f"DEC-2026-{(i + 1):04d}"

            d = Decision.unscoped.create(
                organization=org,
                ref=ref,
                title=title,
                description_md=f"### Contexte\n\nDécision portée par {dir_obj.name} ({sub_name}). "
                               f"Validation en CODIR pour {priority} impact {impact}.\n\n"
                               f"### Motivation\n\n"
                               f"Cette décision s'inscrit dans la stratégie Groupe 2026.",
                meeting=random.choice([
                    m for m in meetings if m.status in (MeetingStatus.COMPLETED, MeetingStatus.IN_PROGRESS)
                ] or meetings),
                direction=dir_obj,
                category=random.choice(list(cats.values())),
                priority=priority,
                impact=impact,
                status=status,
                responsible=responsible,
                deadline=(now + timedelta(days=offset)).date(),
                is_confidential=random.random() < 0.15,
                approved_at=now - timedelta(days=2) if status in (
                    DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS, DecisionStatus.COMPLETED
                ) else None,
                approved_by=dg if status in (
                    DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS, DecisionStatus.COMPLETED
                ) else None,
                completed_at=now - timedelta(days=1) if status == DecisionStatus.COMPLETED else None,
                created_by=dg,
            )
            decisions.append(d)

            DecisionHistory.unscoped.create(
                organization=org, decision=d, actor=dg,
                event="created", description=f"Décision créée : {title}",
            )
            if status != DecisionStatus.PROPOSED:
                DecisionHistory.unscoped.create(
                    organization=org, decision=d, actor=dg,
                    event="approved", description="Validée en CODIR",
                )

            # 1-3 commentaires sur certaines décisions
            if random.random() < 0.4:
                DecisionComment.unscoped.create(
                    organization=org, decision=d,
                    author=random.choice(users_list),
                    body_md=random.choice([
                        "Aligné. Je propose qu'on accélère la mise en œuvre.",
                        "Attention au respect du calendrier RGPD pour cette décision.",
                        "Budget validé. Le DAF confirme la disponibilité de l'enveloppe.",
                        "Demande de complément d'analyse avant la prochaine séance.",
                    ]),
                )
        self.stdout.write(f"  • {len(decisions)} décisions (statuts variés)")

        # ─── Action Plans + Tasks ────────────────────────────
        plans: list[ActionPlan] = []
        # On crée un plan pour ~ 70% des décisions validées/en cours/réalisées
        eligible = [d for d in decisions if d.status in (
            DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS, DecisionStatus.COMPLETED,
        )]
        for d in eligible:
            if random.random() > 0.85:
                continue
            owner = d.responsible or random.choice(users_list)
            status = (
                ActionPlanStatus.COMPLETED if d.status == DecisionStatus.COMPLETED
                else ActionPlanStatus.IN_PROGRESS if d.status == DecisionStatus.IN_PROGRESS
                else ActionPlanStatus.OPEN
            )
            plan = ActionPlan.unscoped.create(
                organization=org, decision=d,
                title=f"Plan d'exécution — {d.title}",
                description_md=f"Plan d'exécution rattaché à la décision {d.ref}.",
                owner=owner,
                start_date=(now - timedelta(days=random.randint(0, 30))).date(),
                target_end_date=d.deadline,
                status=status,
                progress_percent=0,  # recalculé après création des tasks
            )
            plans.append(plan)

            # Tasks — assignées à divers membres
            task_titles = TASK_TEMPLATES_BY_DECISION.get(d.title, random.sample(DEFAULT_TASKS, k=random.randint(3, 5)))
            for j, ttitle in enumerate(task_titles):
                # 30% des tâches assignées au même responsable de la décision,
                # 70% distribuées sur d'autres membres de la même filiale ou d'autres filiales
                if random.random() < 0.3:
                    assignee = owner
                else:
                    assignee = random.choice(users_list)

                # Status
                r = random.random()
                if r < 0.3:   tstatus = ActionTaskStatus.DONE
                elif r < 0.6: tstatus = ActionTaskStatus.IN_PROGRESS
                elif r < 0.78: tstatus = ActionTaskStatus.TODO
                elif r < 0.88: tstatus = ActionTaskStatus.OVERDUE
                elif r < 0.96: tstatus = ActionTaskStatus.BLOCKED
                else:         tstatus = ActionTaskStatus.CANCELLED

                # Échéance : ~30% en retard
                due_offset = random.choice([-7, -3, -1, 3, 7, 14, 21, 30])
                due_date = (now + timedelta(days=due_offset)).date()

                progress = 100 if tstatus == ActionTaskStatus.DONE else random.choice([0, 10, 25, 40, 60, 75, 90])

                task = ActionTask.unscoped.create(
                    organization=org, action_plan=plan,
                    title=ttitle,
                    description_md=f"Étape {j + 1} du plan {plan.title}.",
                    priority=random.choice(list(Priority.values)),
                    status=tstatus,
                    assignee=assignee,
                    due_date=due_date,
                    progress_percent=progress,
                    started_at=now - timedelta(days=random.randint(1, 20)) if progress > 0 else None,
                    completed_at=now - timedelta(days=random.randint(0, 5)) if tstatus == ActionTaskStatus.DONE else None,
                )

                # 20% des tâches ont un commentaire
                if random.random() < 0.2:
                    ActionComment.unscoped.create(
                        organization=org, task=task,
                        author=assignee,
                        body_md=random.choice([
                            "Avancement à 50%, point de blocage côté juridique levé.",
                            "Réunion de cadrage avec le prestataire planifiée pour la semaine prochaine.",
                            "Document de spec rédigé et en relecture chez la DAF.",
                            "Reporté de 5 jours en accord avec le responsable de la décision.",
                        ]),
                    )

            # Recompute du progress du plan
            plan.recompute_progress()
            plan.save(update_fields=["progress_percent", "status", "updated_at"])

        total_tasks = ActionTask.unscoped.filter(organization=org).count()
        self.stdout.write(f"  • {len(plans)} plans d'action — {total_tasks} tâches assignées")

        # ─── Notifications variées ───────────────────────────
        notif_events = [
            NotificationEvent.MEETING_INVITED,
            NotificationEvent.DECISION_APPROVED,
            NotificationEvent.TASK_ASSIGNED,
            NotificationEvent.TASK_OVERDUE,
            NotificationEvent.MEETING_REMINDER,
        ]
        for _ in range(40):
            recipient = random.choice(users_list)
            event = random.choice(notif_events)
            Notification.unscoped.create(
                organization=org, recipient=recipient,
                event=event,
                level=random.choice([
                    NotificationLevel.INFO, NotificationLevel.INFO,
                    NotificationLevel.WARNING, NotificationLevel.SUCCESS,
                    NotificationLevel.DANGER,
                ]),
                title=random.choice([
                    "Vous êtes convoqué·e à la prochaine session CODIR",
                    "Une décision vous a été assignée",
                    "Tâche en retard — action requise",
                    "Plan d'action validé par le Comex",
                    "Échéance dans 48h",
                ]),
                body=random.choice(NOTIF_BODIES),
                seen_at=now - timedelta(hours=random.randint(1, 48)) if random.random() < 0.4 else None,
            )
        self.stdout.write("  • 40 notifications variées")

        # ─── Audit logs ──────────────────────────────────────
        for d in decisions[:10]:
            AuditLog.unscoped.create(
                organization=org, actor=dg,
                action="created",
                description=f"Décision créée : {d.ref}",
                target_repr=d.title,
            )
        for m in meetings[:5]:
            AuditLog.unscoped.create(
                organization=org, actor=dg,
                action="created",
                description=f"Réunion créée : {m.title}",
                target_repr=m.title,
            )
        self.stdout.write("  • Audit logs initiaux")

        # ─── Récap final ─────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("─── Récapitulatif ──────────────────────"))
        for name, sub in subs.items():
            plan_count = ActionPlan.unscoped.filter(
                organization=org, decision__direction__subsidiary=sub,
            ).count()
            task_count = ActionTask.unscoped.filter(
                organization=org, action_plan__decision__direction__subsidiary=sub,
            ).count()
            self.stdout.write(f"  {name:30s} — {plan_count} plans / {task_count} tâches")
        self.stdout.write("")
        self.stdout.write("  Comptes de démo (mdp : Codir!2026) :")
        for u in USERS:
            self.stdout.write(f"    • {u['email']:25s}  {u['first']} {u['last']:12s}  [{u['sub']}]")
