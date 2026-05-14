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
