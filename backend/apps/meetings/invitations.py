"""Service d'envoi d'invitations + pièce jointe ICS pour ajout au calendrier.

Génère un fichier .ics RFC 5545 que Outlook / Google Calendar / Apple Calendar
peuvent importer. Si la réunion a un ``video_url`` (Teams, Zoom, etc.), il est
ajouté en ``URL`` et dans la description.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.meetings.models import Meeting

logger = logging.getLogger(__name__)


def _ics_escape(text: str) -> str:
    """Échappe les caractères spéciaux iCalendar (RFC 5545)."""
    return (
        text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
    )


def _format_utc(dt: datetime) -> str:
    """Convertit un datetime aware en UTC + format iCal."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(meeting: "Meeting", organizer_email: str | None = None) -> str:
    """Construit le contenu .ics pour un Meeting donné.

    Compatible avec Outlook, Google Calendar, Apple Calendar, Teams.
    """
    uid = f"meeting-{meeting.id}@codir.datarium-dev.com"
    organizer = organizer_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@codir.local")

    description_parts = []
    if meeting.description:
        description_parts.append(meeting.description)
    if meeting.video_url:
        description_parts.append(f"\n🎥 Lien Teams/Visio : {meeting.video_url}")
    description_parts.append(
        f"\n📋 Détails et CR : {getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')}"
        f"/meetings/{meeting.id}"
    )
    description = "\n".join(description_parts)

    location = meeting.location or ""
    if meeting.video_url:
        location = f"{location} | {meeting.video_url}".strip(" |")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CODIR Executive//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_format_utc(timezone.now())}",
        f"DTSTART:{_format_utc(meeting.scheduled_start)}",
        f"DTEND:{_format_utc(meeting.scheduled_end)}",
        f"SUMMARY:{_ics_escape(meeting.title)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"LOCATION:{_ics_escape(location)}",
        f"ORGANIZER:mailto:{organizer}",
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_escape(meeting.title)}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    if meeting.video_url:
        # Insérer URL avant END:VEVENT
        lines.insert(-2, f"URL:{meeting.video_url}")

    return "\r\n".join(lines)


def send_meeting_invitation(meeting: "Meeting", recipient: "User") -> bool:
    """Envoie un email d'invitation à un participant avec un fichier .ics joint.

    Returns True si envoyé, False si échec.
    """
    if not recipient.email:
        return False

    site_url = getattr(settings, "FRONTEND_BASE_URL", "https://codir.datarium-dev.com").rstrip("/")
    meeting_url = f"{site_url}/meetings/{meeting.id}"

    start_local = timezone.localtime(meeting.scheduled_start)
    end_local = timezone.localtime(meeting.scheduled_end)

    subject = f"Invitation : {meeting.title}"
    body_text = (
        f"Bonjour {recipient.first_name or recipient.email},\n\n"
        f"Vous êtes invité(e) à la réunion : {meeting.title}\n\n"
        f"📅 Date : {start_local:%A %d %B %Y}\n"
        f"⏰ Horaire : {start_local:%H:%M} – {end_local:%H:%M}\n"
        + (f"📍 Lieu : {meeting.location}\n" if meeting.location else "")
        + (f"🎥 Lien : {meeting.video_url}\n" if meeting.video_url else "")
        + (f"📝 Description :\n{meeting.description}\n\n" if meeting.description else "\n")
        + f"Détails et ordre du jour : {meeting_url}\n\n"
        f"Vous recevrez des rappels 24h puis 1h avant la réunion.\n\n"
        f"— CODIR Executive"
    )

    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 580px; margin: auto; color: #1f2937;">
      <h2 style="color: #ea580c; margin-bottom: 4px;">Invitation à une réunion</h2>
      <h3 style="margin: 0 0 16px 0;">{meeting.title}</h3>

      <table style="width: 100%; margin: 16px 0; font-size: 14px;">
        <tr><td style="padding: 6px 0; color: #6b7280;">📅 Date</td>
            <td style="padding: 6px 0;"><strong>{start_local:%A %d %B %Y}</strong></td></tr>
        <tr><td style="padding: 6px 0; color: #6b7280;">⏰ Horaire</td>
            <td style="padding: 6px 0;">{start_local:%H:%M} – {end_local:%H:%M}</td></tr>
        {f'<tr><td style="padding: 6px 0; color: #6b7280;">📍 Lieu</td><td style="padding: 6px 0;">{meeting.location}</td></tr>' if meeting.location else ''}
        {f'<tr><td style="padding: 6px 0; color: #6b7280;">🎥 Lien</td><td style="padding: 6px 0;"><a href="{meeting.video_url}" style="color: #ea580c;">Rejoindre la visio</a></td></tr>' if meeting.video_url else ''}
      </table>

      {f'<div style="background: #f9fafb; padding: 12px 16px; border-radius: 8px; margin: 16px 0; font-size: 13px;">{meeting.description}</div>' if meeting.description else ''}

      <p style="margin: 24px 0;">
        <a href="{meeting_url}"
           style="background: #ea580c; color: white; padding: 10px 20px;
                  text-decoration: none; border-radius: 6px; font-weight: 600;">
          Ouvrir dans CODIR
        </a>
      </p>

      <p style="color: #6b7280; font-size: 12px; margin-top: 32px;">
        Pour ajouter cette réunion à votre calendrier (Outlook, Google, Apple),
        ouvrez le fichier <code>invitation.ics</code> joint à cet email.<br/>
        Vous recevrez des rappels 24h puis 1h avant la réunion.
      </p>

      <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 24px 0;" />
      <p style="color: #9ca3af; font-size: 11px; text-align: center;">CODIR Executive · Kaydan</p>
    </div>
    """

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=[recipient.email],
    )
    msg.attach_alternative(html_body, "text/html")

    # ICS attachment (Content-Type spécifique pour Outlook/Teams)
    ics_content = build_ics(meeting, organizer_email=from_email)
    msg.attach("invitation.ics", ics_content, "text/calendar; method=REQUEST")

    # Headers anti-spam + threading
    site_domain = (from_email or "noreply@codir.local").rsplit("@", 1)[-1].strip(">")
    msg.extra_headers = {
        "Message-ID": f"<meeting-{meeting.id}-{recipient.id}@{site_domain}>",
        "X-Entity-Ref-ID": str(meeting.id),
        "Auto-Submitted": "auto-generated",
    }

    try:
        msg.send(fail_silently=False)
        logger.info("Invitation sent: %s → %s", meeting.id, recipient.email)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send invitation for meeting=%s to %s",
                         meeting.id, recipient.email)
        return False


def send_invitations_for_meeting(meeting: "Meeting") -> int:
    """Envoie une invitation à tous les participants d'un Meeting.

    Returns: nombre d'invitations envoyées avec succès.
    """
    sent = 0
    for participant in meeting.participants.select_related("user").all():
        if participant.user and participant.user.email:
            if send_meeting_invitation(meeting, participant.user):
                sent += 1
    return sent
