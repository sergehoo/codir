"""Briefing matinal personnalisé — Lot 4.

Compose un texte court adapté à la lecture vocale (Web Speech API navigateur,
100% gratuit côté frontend) avec les informations critiques du jour :
  - Salutation contextualisée (matin/midi/soir)
  - Mes tâches dues aujourd'hui et demain
  - Mes réunions du jour
  - Décisions en attente que je dois trancher
  - Top sujets à risque qui me concernent (santé < 60)

Format :
  - `markdown` : version riche pour affichage à l'écran
  - `vocal_text` : version simplifiée pour TTS — phrases courtes, ponctuation
    claire, sans markdown ni emoji susceptible d'être prononcé.
  - `summary` : 1 phrase de synthèse pour notification.

Sans appel LLM (déterministe, instantané, gratuit). Si Claude est disponible
on peut enrichir plus tard via une couche optionnelle (Lot 4 bis).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.utils import timezone


def _greeting_for_now() -> str:
    """Salutation contextualisée au moment de la journée."""
    h = timezone.localtime().hour
    if h < 6:   return "Bonne nuit"
    if h < 12:  return "Bonjour"
    if h < 18:  return "Bon après-midi"
    return "Bonsoir"


def _format_due(due_date, today) -> str:
    """Formate une échéance en français pour la lecture vocale."""
    if not due_date:
        return "sans date"
    days = (due_date - today).days
    if days == 0:    return "pour aujourd'hui"
    if days == 1:    return "pour demain"
    if days == -1:   return "en retard d'un jour"
    if days < 0:     return f"en retard de {-days} jours"
    if days <= 7:    return f"dans {days} jours"
    return f"le {due_date.strftime('%d/%m')}"


def generate_daily_briefing(*, user, organization) -> dict:
    """Génère le briefing matinal pour ce user dans cette org.

    Retourne :
        {
          "markdown": "..._affichage_HTML_...",
          "vocal_text": "...lecture_TTS...",
          "summary":  "Vous avez X tâches dues aujourd'hui...",
          "generated_at": ISO datetime,
          "stats": { my_tasks_today, meetings_today, decisions_pending, at_risk },
        }
    """
    from apps.action_plans.models import ActionTask
    from apps.common.enums import ActionTaskStatus
    from apps.common.health_score import build_watchlist
    from apps.decisions.models import Decision
    from apps.meetings.models import Meeting

    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    end_of_today = now.replace(hour=23, minute=59, second=59)

    user_name = (user.first_name or user.email.split("@")[0] or "").strip()
    org_name = getattr(organization, "name", "") or ""
    greeting = _greeting_for_now()

    # ── 1. Mes tâches dues aujourd'hui ou demain ──
    my_tasks = list(
        ActionTask.unscoped
        .filter(
            organization=organization,
            assignee=user,
            due_date__lte=tomorrow,
        )
        .exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
        .order_by("due_date")[:10]
    )

    # ── 2. Mes réunions du jour ──
    meetings_today = list(
        Meeting.unscoped
        .filter(
            organization=organization,
            scheduled_start__gte=now,
            scheduled_start__lte=end_of_today,
        )
        .exclude(status="cancelled")
        .order_by("scheduled_start")[:5]
    )

    # ── 3. Décisions en attente où je suis responsable ──
    my_decisions = list(
        Decision.unscoped
        .filter(
            organization=organization,
            responsible=user,
            status__in=["proposed", "in_review"],
        )
        .order_by("deadline", "-priority")[:5]
    )

    # ── 4. Top sujets à risque qui me concernent ──
    watchlist = build_watchlist(organization=organization, limit=20)
    # Filtre sur les items où je suis owner/responsible (heuristique simple
    # via owner_name = mon nom). C'est approximatif mais suffisant pour
    # un briefing — l'agent proactif fait le tri fin.
    my_full_name = (user.get_full_name() if hasattr(user, "get_full_name")
                    else user.email).strip()
    at_risk_mine = [
        w for w in watchlist
        if my_full_name and my_full_name.lower() in (w.get("owner_name") or "").lower()
    ][:3]

    # ─── Composition markdown + vocal_text ─────────────────────
    md_parts: list[str] = []
    vocal_parts: list[str] = []

    # Salutation
    salutation = f"{greeting}{' ' + user_name if user_name else ''}."
    md_parts.append(f"## {salutation}")
    vocal_parts.append(salutation)

    if org_name:
        intro = f"Voici votre briefing du jour pour {org_name}."
    else:
        intro = "Voici votre briefing du jour."
    md_parts.append(intro)
    vocal_parts.append(intro)

    # Pas grand chose → message court
    nothing_to_report = (
        not my_tasks and not meetings_today and not my_decisions and not at_risk_mine
    )
    if nothing_to_report:
        peaceful = "Aucune urgence détectée. Bonne journée."
        md_parts.append(f"\n{peaceful}")
        vocal_parts.append(peaceful)
        return _assemble(md_parts, vocal_parts, {
            "my_tasks_today": 0, "meetings_today": 0,
            "decisions_pending": 0, "at_risk": 0,
        })

    # Tâches
    if my_tasks:
        md_parts.append(f"\n### Vos tâches ({len(my_tasks)})")
        if len(my_tasks) == 1:
            vocal_parts.append("Vous avez une tâche à traiter.")
        else:
            vocal_parts.append(f"Vous avez {len(my_tasks)} tâches à traiter.")
        for t in my_tasks[:5]:
            due_str = _format_due(t.due_date, today)
            title = (t.title or "(sans titre)").strip()
            # Markdown
            md_parts.append(f"- **{title}** — {due_str}")
            # Vocal — phrase complète
            vocal_parts.append(f"{title}, {due_str}.")
        if len(my_tasks) > 5:
            md_parts.append(f"- … et {len(my_tasks) - 5} autres.")
            vocal_parts.append(f"Et {len(my_tasks) - 5} autres tâches.")

    # Réunions
    if meetings_today:
        md_parts.append(f"\n### Vos réunions aujourd'hui ({len(meetings_today)})")
        if len(meetings_today) == 1:
            vocal_parts.append("Vous avez une réunion aujourd'hui.")
        else:
            vocal_parts.append(f"Vous avez {len(meetings_today)} réunions aujourd'hui.")
        for m in meetings_today:
            t_str = m.scheduled_start.strftime("%H heures %M") if m.scheduled_start else ""
            t_str = t_str.replace(" 00", "").strip()
            title = (m.title or "Réunion").strip()
            md_parts.append(f"- **{title}** — {t_str}")
            vocal_parts.append(f"{title} à {t_str}.")

    # Décisions
    if my_decisions:
        md_parts.append(f"\n### Décisions à trancher ({len(my_decisions)})")
        if len(my_decisions) == 1:
            vocal_parts.append("Une décision attend votre arbitrage.")
        else:
            vocal_parts.append(f"{len(my_decisions)} décisions attendent votre arbitrage.")
        for d in my_decisions[:3]:
            title = (d.title or "(sans titre)").strip()
            deadline_str = ""
            if d.deadline:
                deadline_str = f" — échéance {_format_due(d.deadline, today)}"
            md_parts.append(f"- **{title}**{deadline_str}")
            vocal_parts.append(f"{title}{deadline_str}.")

    # Sujets à risque
    if at_risk_mine:
        md_parts.append(f"\n### Sujets à surveiller ({len(at_risk_mine)})")
        if len(at_risk_mine) == 1:
            vocal_parts.append("Un sujet mérite votre attention.")
        else:
            vocal_parts.append(f"{len(at_risk_mine)} sujets méritent votre attention.")
        for w in at_risk_mine:
            kind_label = "Plan" if w["kind"] == "plan" else "Décision"
            title = (w.get("title") or "").strip()
            reason = (w.get("reasons", [""])[0] or "").strip()
            md_parts.append(f"- **{title}** ({kind_label}) — {reason}")
            vocal_parts.append(f"{title}. {reason}.")

    # Closing
    if my_tasks or meetings_today or my_decisions:
        closing = "Bonne journée."
        md_parts.append(f"\n{closing}")
        vocal_parts.append(closing)

    return _assemble(md_parts, vocal_parts, {
        "my_tasks_today":    len(my_tasks),
        "meetings_today":    len(meetings_today),
        "decisions_pending": len(my_decisions),
        "at_risk":           len(at_risk_mine),
    })


def _assemble(md_parts, vocal_parts, stats) -> dict:
    """Construit la sortie finale du briefing."""
    markdown = "\n".join(md_parts).strip()
    # Pour la lecture vocale on assemble avec espaces (ne pas multiplier les
    # pauses, sinon le TTS marque des silences gênants) et on nettoie quelques
    # caractères qui se prononcent mal.
    vocal_text = " ".join(p.strip() for p in vocal_parts if p.strip())
    vocal_text = (
        vocal_text
        .replace("…", " etc.")
        .replace("—", ",")
        .replace("**", "")
        .replace("`", "")
    )
    summary_parts = []
    if stats["my_tasks_today"]:    summary_parts.append(f"{stats['my_tasks_today']} tâche(s)")
    if stats["meetings_today"]:    summary_parts.append(f"{stats['meetings_today']} réunion(s)")
    if stats["decisions_pending"]: summary_parts.append(f"{stats['decisions_pending']} décision(s)")
    if stats["at_risk"]:           summary_parts.append(f"{stats['at_risk']} alerte(s)")
    summary = ("Au programme aujourd'hui : " + ", ".join(summary_parts) + ".") if summary_parts else "Aucune urgence détectée."

    return {
        "markdown":     markdown,
        "vocal_text":   vocal_text,
        "summary":      summary,
        "generated_at": timezone.now().isoformat(),
        "stats":        stats,
    }
