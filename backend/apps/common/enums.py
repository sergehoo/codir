"""Enums partagés bêta — statuts, priorités, impacts."""
from django.db import models


class Priority(models.TextChoices):
    LOW = "low", "Faible"
    MEDIUM = "medium", "Moyenne"
    HIGH = "high", "Élevée"
    CRITICAL = "critical", "Critique"


class ImpactLevel(models.TextChoices):
    LOW = "low", "Faible"
    MEDIUM = "medium", "Moyen"
    HIGH = "high", "Fort"
    STRATEGIC = "strategic", "Stratégique"


class MeetingStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SCHEDULED = "scheduled", "Planifiée"
    IN_PROGRESS = "in_progress", "En cours"
    COMPLETED = "completed", "Terminée"
    CANCELLED = "cancelled", "Annulée"


class AgendaItemStatus(models.TextChoices):
    PENDING = "pending", "À traiter"
    IN_PROGRESS = "in_progress", "En cours"
    DISCUSSED = "discussed", "Traité"
    POSTPONED = "postponed", "Reporté"
    CANCELLED = "cancelled", "Annulé"


class DecisionStatus(models.TextChoices):
    PROPOSED = "proposed", "Proposée"
    APPROVED = "approved", "Validée"
    IN_PROGRESS = "in_progress", "En exécution"
    COMPLETED = "completed", "Réalisée"
    CANCELLED = "cancelled", "Annulée"
    POSTPONED = "postponed", "Reportée"


class ActionPlanStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    IN_PROGRESS = "in_progress", "En cours"
    COMPLETED = "completed", "Terminé"
    BLOCKED = "blocked", "Bloqué"
    CANCELLED = "cancelled", "Annulé"


class ActionTaskStatus(models.TextChoices):
    TODO = "todo", "À faire"
    IN_PROGRESS = "in_progress", "En cours"
    DONE = "done", "Fait"
    BLOCKED = "blocked", "Bloqué"
    OVERDUE = "overdue", "En retard"
    CANCELLED = "cancelled", "Annulé"


class AttendanceStatus(models.TextChoices):
    INVITED = "invited", "Invité"
    ACCEPTED = "accepted", "Accepté"
    DECLINED = "declined", "Refusé"
    PRESENT = "present", "Présent"
    ABSENT = "absent", "Absent"
    LATE = "late", "En retard"


class ParticipantRole(models.TextChoices):
    CHAIR = "chair", "Président"
    SECRETARY = "secretary", "Secrétaire"
    MEMBER = "member", "Membre"
    INVITED = "invited", "Invité"
    OBSERVER = "observer", "Observateur"
