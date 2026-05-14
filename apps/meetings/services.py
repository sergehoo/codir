"""Services métier — meetings."""
from django.db import transaction
from django.utils import timezone

from apps.common.enums import (
    AttendanceStatus, MeetingStatus, ParticipantRole,
)
from apps.common.exceptions import MeetingLocked, TransitionNotAllowed

from .models import Meeting, MeetingAttendance, MeetingParticipant, MeetingMinutes


@transaction.atomic
def create_meeting(*, organization, created_by, data: dict) -> Meeting:
    meeting = Meeting.unscoped.create(
        organization=organization, created_by=created_by, **data,
    )
    # Auto-ajouter chair + secretary comme participants
    for user, role in (
        (meeting.chair, ParticipantRole.CHAIR),
        (meeting.secretary, ParticipantRole.SECRETARY),
    ):
        if user is not None:
            MeetingParticipant.unscoped.get_or_create(
                organization=organization, meeting=meeting, user=user,
                defaults={"role": role},
            )
    return meeting


@transaction.atomic
def add_participant(meeting: Meeting, *, user=None, external_email=None, external_name="",
                    role: str = ParticipantRole.MEMBER) -> MeetingParticipant:
    if meeting.is_locked:
        raise MeetingLocked()
    part = MeetingParticipant.unscoped.create(
        organization=meeting.organization,
        meeting=meeting, user=user,
        external_email=external_email or None,
        external_name=external_name, role=role,
    )
    MeetingAttendance.unscoped.create(
        organization=meeting.organization,
        meeting=meeting, participant=part, status=AttendanceStatus.INVITED,
    )
    return part


@transaction.atomic
def start_meeting(meeting: Meeting, *, by_user) -> Meeting:
    if meeting.status != MeetingStatus.SCHEDULED:
        raise TransitionNotAllowed(
            detail=f"Une réunion doit être 'planifiée' pour être démarrée (statut={meeting.status})."
        )
    if not getattr(meeting, "agenda", None) or not meeting.agenda.is_validated:
        raise TransitionNotAllowed(
            detail="L'ordre du jour doit être validé avant de démarrer la réunion."
        )
    meeting.status = MeetingStatus.IN_PROGRESS
    meeting.actual_start = timezone.now()
    meeting.save(update_fields=["status", "actual_start", "updated_at"])
    return meeting


@transaction.atomic
def complete_meeting(meeting: Meeting, *, by_user) -> Meeting:
    if meeting.status != MeetingStatus.IN_PROGRESS:
        raise TransitionNotAllowed(
            detail=f"Seule une réunion 'en cours' peut être clôturée (statut={meeting.status})."
        )
    if meeting.quorum_min:
        present = meeting.attendances.filter(status=AttendanceStatus.PRESENT).count()
        meeting.quorum_reached = present >= meeting.quorum_min
    meeting.status = MeetingStatus.COMPLETED
    meeting.actual_end = timezone.now()
    meeting.save(update_fields=["status", "actual_end", "quorum_reached", "updated_at"])
    _generate_minutes(meeting, by_user)
    return meeting


@transaction.atomic
def cancel_meeting(meeting: Meeting, *, by_user, reason: str = "") -> Meeting:
    if meeting.status == MeetingStatus.COMPLETED:
        raise MeetingLocked(detail="Une réunion terminée ne peut être annulée.")
    meeting.status = MeetingStatus.CANCELLED
    if reason:
        meeting.final_notes_md = (meeting.final_notes_md + f"\n\n**Motif d'annulation** : {reason}").strip()
    meeting.save(update_fields=["status", "final_notes_md", "updated_at"])
    return meeting


@transaction.atomic
def record_attendance(meeting: Meeting, *, participant_id, status: str,
                      arrived_at=None, recorded_by=None) -> MeetingAttendance:
    if meeting.status not in {MeetingStatus.IN_PROGRESS, MeetingStatus.SCHEDULED}:
        raise TransitionNotAllowed(
            detail="Présence enregistrable uniquement si la réunion est planifiée ou en cours."
        )
    att, _ = MeetingAttendance.unscoped.update_or_create(
        organization=meeting.organization,
        meeting=meeting, participant_id=participant_id,
        defaults={"status": status, "arrived_at": arrived_at, "recorded_by": recorded_by},
    )
    return att


def _generate_minutes(meeting: Meeting, generated_by) -> MeetingMinutes:
    """Génère un compte rendu HTML simple à la clôture."""
    parts = list(meeting.participants.select_related("user").all())
    present_ids = {
        a.participant_id for a in meeting.attendances.filter(status=AttendanceStatus.PRESENT)
    }
    items = list(getattr(meeting, "agenda", None).items.all()) if hasattr(meeting, "agenda") else []
    decisions = list(meeting.decisions.all()) if hasattr(meeting, "decisions") else []

    def _label(p):
        return p.user.get_full_name() if p.user else (p.external_name or p.external_email)

    html = ["<article class='minutes'>"]
    html.append(f"<h1>Compte rendu — {meeting.title}</h1>")
    html.append(f"<p><strong>Date</strong> : {meeting.scheduled_start:%d/%m/%Y %H:%M} → {meeting.scheduled_end:%H:%M}</p>")
    html.append(f"<p><strong>Lieu / Lien</strong> : {meeting.location or meeting.video_url or '—'}</p>")
    html.append(f"<p><strong>Président</strong> : {meeting.chair.get_full_name() if meeting.chair else '—'}<br>")
    html.append(f"<strong>Secrétaire</strong> : {meeting.secretary.get_full_name() if meeting.secretary else '—'}</p>")

    presents = [p for p in parts if p.id in present_ids]
    absents = [p for p in parts if p.id not in present_ids]
    html.append("<h2>Participants présents</h2><ul>")
    for p in presents:
        html.append(f"<li>{_label(p)} — {p.get_role_display()}</li>")
    html.append("</ul>")
    if absents:
        html.append("<h2>Absents / Excusés</h2><ul>")
        for p in absents:
            html.append(f"<li>{_label(p)}</li>")
        html.append("</ul>")

    if items:
        html.append("<h2>Ordre du jour</h2><ol>")
        for it in items:
            html.append(f"<li><strong>{it.title}</strong> — {it.get_status_display()}")
            if it.discussion_notes_md:
                html.append(f"<div>{it.discussion_notes_md}</div>")
            html.append("</li>")
        html.append("</ol>")

    if decisions:
        html.append("<h2>Décisions actées</h2><ul>")
        for d in decisions:
            resp = d.responsible.get_full_name() if d.responsible else "—"
            deadline = d.deadline.strftime("%d/%m/%Y") if d.deadline else "—"
            html.append(f"<li><code>{d.ref}</code> <strong>{d.title}</strong> — Resp. {resp} · Échéance {deadline} · {d.get_status_display()}</li>")
        html.append("</ul>")

    if meeting.final_notes_md:
        html.append("<h2>Notes finales</h2>")
        html.append(f"<div>{meeting.final_notes_md}</div>")

    # ─── Signature de pied de page ─────────────────────────
    html.append(
        "<div style='margin-top:3rem;padding-top:1.5rem;"
        "border-top:1px solid #e5e5e5;text-align:center;'>"
        "<p style='font-size:11px;color:#888;letter-spacing:0.18em;"
        "text-transform:uppercase;margin:0 0 0.75rem 0;'>"
        "Compte rendu généré par CODIR Executive Platform"
        "</p>"
        "<p style='font-size:11px;letter-spacing:0.18em;"
        "text-transform:uppercase;margin:0;'>"
        "<span style='color:#888;'>Édité par&nbsp;</span>"
        "<strong style='color:#0A0A0A;'>KAYDAN</strong>&nbsp;"
        "<em style='color:#555;font-weight:500;'>Groupe</em>"
        "&nbsp;·&nbsp;"
        "<span style='color:#F97316;font-weight:700;'>Digital &amp; Technologies</span>"
        "</p>"
        "</div>"
    )
    html.append("</article>")
    body_html = "\n".join(html)

    minutes, _ = MeetingMinutes.unscoped.update_or_create(
        organization=meeting.organization, meeting=meeting,
        defaults={
            "title": f"PV — {meeting.title}",
            "body_html": body_html,
            "generated_by": generated_by,
        },
    )
    meeting.minutes_generated_at = timezone.now()
    meeting.save(update_fields=["minutes_generated_at", "updated_at"])
    return minutes
