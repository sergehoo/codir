"""Services métier — agendas."""
from django.db import transaction
from django.utils import timezone

from apps.common.enums import AgendaItemStatus, MeetingStatus
from apps.common.exceptions import MeetingLocked, TransitionNotAllowed

from .models import Agenda, AgendaItem


@transaction.atomic
def get_or_create_agenda(*, meeting) -> Agenda:
    agenda, _ = Agenda.unscoped.get_or_create(
        organization=meeting.organization, meeting=meeting,
    )
    return agenda


@transaction.atomic
def add_item(*, agenda: Agenda, data: dict, created_by=None) -> AgendaItem:
    if agenda.is_validated:
        raise TransitionNotAllowed(detail="L'ordre du jour est validé, plus de modifications.")
    if agenda.meeting.is_locked:
        raise MeetingLocked()
    last_order = agenda.items.order_by("-order").values_list("order", flat=True).first() or 0
    return AgendaItem.unscoped.create(
        organization=agenda.organization,
        agenda=agenda, order=last_order + 1, **data,
    )


@transaction.atomic
def reorder_items(*, agenda: Agenda, ordered_ids: list[str]) -> None:
    if agenda.is_validated:
        raise TransitionNotAllowed(detail="L'ordre du jour est validé.")
    for idx, pk in enumerate(ordered_ids):
        AgendaItem.unscoped.filter(agenda=agenda, id=pk).update(order=idx + 1)


@transaction.atomic
def validate_agenda(*, agenda: Agenda, validator) -> Agenda:
    if agenda.is_validated:
        return agenda
    if agenda.items.count() == 0:
        raise TransitionNotAllowed(detail="Impossible de valider un ordre du jour vide.")
    agenda.is_validated = True
    agenda.validated_at = timezone.now()
    agenda.validated_by = validator
    agenda.save(update_fields=["is_validated", "validated_at", "validated_by", "updated_at"])
    # Si la réunion est en brouillon, on la passe à scheduled
    if agenda.meeting.status == MeetingStatus.DRAFT:
        agenda.meeting.status = MeetingStatus.SCHEDULED
        agenda.meeting.save(update_fields=["status", "updated_at"])
    return agenda


@transaction.atomic
def discuss_item(*, item: AgendaItem, notes_md: str = "", actor=None) -> AgendaItem:
    if item.status == AgendaItemStatus.DISCUSSED:
        return item
    if item.started_at is None:
        item.started_at = timezone.now()
    item.status = AgendaItemStatus.DISCUSSED
    item.completed_at = timezone.now()
    if notes_md:
        item.discussion_notes_md = notes_md
    item.save()
    return item


@transaction.atomic
def postpone_item(*, item: AgendaItem, reason: str = "", actor=None) -> AgendaItem:
    item.status = AgendaItemStatus.POSTPONED
    if reason:
        item.discussion_notes_md = (item.discussion_notes_md + f"\n\n_Reporté_: {reason}").strip()
    item.save()
    return item


@transaction.atomic
def copy_items_from_previous_meeting(*, agenda: Agenda) -> dict:
    """Copie les items NON-clôturés de la séance précédente de la même série.

    Cas d'usage : CODIR récurrent. Au lieu de retaper l'ODJ chaque semaine,
    on hérite des items pending/postponed de la séance précédente.

    Critères de la "séance précédente" :
    - Même `MeetingSeries` que la réunion courante.
    - `scheduled_start` < `current.scheduled_start`.
    - Statut COMPLETED ou IN_PROGRESS (pas DRAFT/CANCELLED).
    - On prend la plus récente correspondant à ces critères.

    Items copiés :
    - Status PENDING ou POSTPONED → reportés en PENDING.
    - Status DISCUSSED ou CANCELLED → ignorés (déjà traités).

    Champs copiés : title, description_md, priority, estimated_duration_minutes,
    responsible. PAS started_at, completed_at, discussion_notes_md (reset).

    Comportement :
    - Si l'agenda courant a déjà des items, on append à la fin (pas de doublon
      side-effect sauf si le caller souhaite vraiment, mais on ne dédupe pas).
    - Si la réunion n'est pas issue d'une série, ou pas de séance précédente
      trouvée, on retourne {"copied": 0, "source": None} sans erreur.

    Retour : { copied: int, source_meeting_id: str|None, source_meeting_title: str }
    """
    if agenda.is_validated:
        raise TransitionNotAllowed(detail="L'ordre du jour est validé.")
    if agenda.meeting.is_locked:
        raise MeetingLocked()

    meeting = agenda.meeting
    if not meeting.series_id:
        return {"copied": 0, "source_meeting_id": None, "source_meeting_title": ""}

    # Recherche de la séance précédente DANS la même série.
    # Import local pour éviter cycle d'import apps.meetings <-> apps.agendas.
    from apps.meetings.models import Meeting

    previous = (
        Meeting.unscoped
        .filter(
            organization=meeting.organization,
            series_id=meeting.series_id,
            scheduled_start__lt=meeting.scheduled_start,
            status__in=[MeetingStatus.COMPLETED, MeetingStatus.IN_PROGRESS],
        )
        .exclude(id=meeting.id)
        .order_by("-scheduled_start")
        .first()
    )
    if previous is None:
        return {"copied": 0, "source_meeting_id": None, "source_meeting_title": ""}

    # Récupère l'agenda de la séance précédente (s'il existe).
    previous_agenda = Agenda.unscoped.filter(meeting=previous).first()
    if previous_agenda is None:
        return {
            "copied": 0,
            "source_meeting_id": str(previous.id),
            "source_meeting_title": previous.title,
        }

    # Items à reporter : pending + postponed (les "vivants")
    to_copy = list(
        previous_agenda.items
        .filter(status__in=[AgendaItemStatus.PENDING, AgendaItemStatus.POSTPONED])
        .order_by("order")
    )
    if not to_copy:
        return {
            "copied": 0,
            "source_meeting_id": str(previous.id),
            "source_meeting_title": previous.title,
        }

    last_order = (
        agenda.items.order_by("-order").values_list("order", flat=True).first() or 0
    )
    bulk = []
    for i, src in enumerate(to_copy, start=1):
        bulk.append(AgendaItem(
            organization=agenda.organization,
            agenda=agenda,
            order=last_order + i,
            title=src.title,
            description_md=src.description_md,
            priority=src.priority,
            estimated_duration_minutes=src.estimated_duration_minutes,
            responsible_id=src.responsible_id,
            status=AgendaItemStatus.PENDING,  # reset : nouveau cycle
        ))
    AgendaItem.unscoped.bulk_create(bulk, batch_size=200)
    return {
        "copied": len(bulk),
        "source_meeting_id": str(previous.id),
        "source_meeting_title": previous.title,
    }
