"""Briefing matinal personnalisé — version étendue & intelligente.

Compose un texte structuré et adapté à la lecture vocale (Web Speech API
navigateur) avec 8 sections riches :

  1. **Tagline** (optionnellement IA) — 1 phrase qui synthétise la journée
  2. **Mes tâches** — dues aujourd'hui, demain, cette semaine, en retard
  3. **Réunions** — du jour + 7 prochains jours, avec contexte (chair/secrétaire)
  4. **Décisions à arbitrer** — où je suis responsable
  5. **Sujets à surveiller** — plans qui dérivent (health_score < 60)
  6. **Activité récente de l'organisation** — dernières décisions / CR / plans
  7. **Indicateurs** — EPI score actuel et tendance
  8. **Équipe** (si manager) — résumé de la charge de l'équipe

Toujours `markdown` (riche) + `vocal_text` (TTS-friendly) + `summary` (1 phrase).
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _greeting_for_now() -> str:
    """Salutation contextualisée au moment de la journée."""
    h = timezone.localtime().hour
    if h < 5:    return "Bonne nuit"
    if h < 12:   return "Bonjour"
    if h < 18:   return "Bon après-midi"
    return "Bonsoir"


def _format_due(due_date, today) -> str:
    """Formate une échéance en français pour la lecture vocale."""
    if not due_date:
        return "sans date"
    days = (due_date - today).days
    if days == 0:    return "pour aujourd'hui"
    if days == 1:    return "pour demain"
    if days == 2:    return "dans 2 jours"
    if days < 0:     return f"en retard de {-days} jour{'s' if -days > 1 else ''}"
    if days <= 7:    return f"dans {days} jours"
    if days <= 14:   return f"la semaine prochaine"
    return f"le {due_date.strftime('%d/%m')}"


def _is_manager(user, organization) -> bool:
    """Détecte si le user supervise une équipe (head de direction ou owner)."""
    try:
        from apps.governance.models import Direction
        if Direction.objects.filter(head=user).exists():
            return True
        if hasattr(user, "memberships"):
            return user.memberships.filter(
                organization=organization, is_owner=True, is_active=True,
            ).exists()
    except Exception:  # noqa: BLE001
        pass
    return False


def generate_daily_briefing(*, user, organization) -> dict:
    """Génère le briefing matinal pour ce user dans cette org.

    Returns un dict riche :
        {
          "markdown": "...affichage écran...",
          "vocal_text": "...lecture TTS...",
          "summary":  "Une phrase d'accroche.",
          "tagline":  "Phrase IA (optionnelle).",
          "generated_at": ISO datetime,
          "stats": { ... 12 compteurs ... },
        }
    """
    from apps.action_plans.models import ActionPlan, ActionTask
    from apps.common.enums import ActionTaskStatus
    from apps.common.health_score import build_watchlist
    from apps.decisions.models import Decision
    from apps.meetings.models import Meeting

    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    end_of_today = now.replace(hour=23, minute=59, second=59)
    in_week = now + timedelta(days=7)

    user_name = (user.first_name or user.email.split("@")[0] or "").strip()
    org_name = getattr(organization, "name", "") or ""
    greeting = _greeting_for_now()
    is_manager = _is_manager(user, organization)

    # ── 1. Mes tâches dues aujourd'hui / demain / cette semaine / en retard ──
    my_active = ActionTask.unscoped.filter(
        organization=organization, assignee=user,
    ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])

    tasks_overdue   = list(my_active.filter(due_date__lt=today)
                                     .order_by("due_date")[:5])
    tasks_today     = list(my_active.filter(due_date=today)[:5])
    tasks_tomorrow  = list(my_active.filter(due_date=tomorrow)[:5])
    tasks_this_week = list(my_active.filter(due_date__gt=tomorrow,
                                            due_date__lte=today + timedelta(days=7))
                                     .order_by("due_date")[:5])

    # ── 2. Mes réunions du jour + 7j ──
    meetings_today = list(
        Meeting.unscoped
        .filter(organization=organization,
                scheduled_start__gte=now, scheduled_start__lte=end_of_today)
        .exclude(status="cancelled")
        .order_by("scheduled_start")[:5]
    )
    meetings_week = list(
        Meeting.unscoped
        .filter(organization=organization,
                scheduled_start__gt=end_of_today, scheduled_start__lte=in_week)
        .exclude(status="cancelled")
        .order_by("scheduled_start")[:5]
    )

    # ── 3. Décisions où je suis responsable ──
    my_decisions = list(
        Decision.unscoped
        .filter(organization=organization, responsible=user,
                status__in=["proposed", "in_review"])
        .order_by("deadline", "-priority")[:5]
    )

    # ── 4. Sujets à risque qui me concernent (filtre via owner_name) ──
    watchlist = build_watchlist(organization=organization, limit=20)
    my_full_name = (user.get_full_name() if hasattr(user, "get_full_name")
                    else user.email).strip()
    at_risk_mine = [
        w for w in watchlist
        if my_full_name and my_full_name.lower() in (w.get("owner_name") or "").lower()
    ][:3]

    # ── 5. Activité récente de l'organisation ──
    recent_decisions = list(
        Decision.unscoped
        .filter(organization=organization, status__in=["approved", "implemented"])
        .order_by("-updated_at")[:3]
    )
    recent_plans = list(
        ActionPlan.unscoped
        .filter(organization=organization)
        .order_by("-created_at")[:3]
    )

    # ── 6. Indicateurs ──
    epi_data = _load_epi_summary(organization=organization)

    # ── 7. Équipe (si manager) ──
    team_summary = _load_team_summary(user=user, organization=organization) if is_manager else None

    # ── Construction markdown + vocal_text ──
    md_parts: list[str] = []
    vocal_parts: list[str] = []

    # Salutation
    salutation = f"{greeting}{' ' + user_name if user_name else ''}."
    md_parts.append(f"## {salutation}")
    vocal_parts.append(salutation)

    intro = (f"Voici votre briefing exécutif pour {org_name}."
             if org_name else "Voici votre briefing exécutif.")
    md_parts.append(intro)
    vocal_parts.append(intro)

    # ── Tagline IA (best-effort, fallback) ──
    tagline = _generate_tagline(
        user_first=user_name,
        org_name=org_name,
        tasks_overdue=len(tasks_overdue),
        tasks_today=len(tasks_today),
        meetings_today=len(meetings_today),
        my_decisions=len(my_decisions),
        at_risk=len(at_risk_mine),
    )
    if tagline:
        md_parts.append(f"\n> _{tagline}_")
        vocal_parts.append(tagline)

    # ── Section 1 — Mes tâches ──
    total_tasks = len(tasks_overdue) + len(tasks_today) + len(tasks_tomorrow) + len(tasks_this_week)
    if total_tasks > 0:
        md_parts.append("\n### 📋 Vos tâches")
        if tasks_overdue:
            md_parts.append(f"\n**⚠ {len(tasks_overdue)} en retard**")
            vocal_parts.append(f"Attention, vous avez {len(tasks_overdue)} tâche{'s' if len(tasks_overdue) > 1 else ''} en retard.")
            for t in tasks_overdue[:3]:
                md_parts.append(f"- **{t.title[:80]}** — {_format_due(t.due_date, today)}")
                vocal_parts.append(f"{t.title[:80]}, {_format_due(t.due_date, today)}.")
            if len(tasks_overdue) > 3:
                md_parts.append(f"- … et {len(tasks_overdue) - 3} autre(s).")

        if tasks_today:
            md_parts.append(f"\n**Aujourd'hui ({len(tasks_today)})**")
            vocal_parts.append(f"Aujourd'hui, {len(tasks_today)} tâche{'s' if len(tasks_today) > 1 else ''}.")
            for t in tasks_today:
                md_parts.append(f"- **{t.title[:80]}**")
                vocal_parts.append(f"{t.title[:80]}.")

        if tasks_tomorrow:
            md_parts.append(f"\n**Demain ({len(tasks_tomorrow)})**")
            for t in tasks_tomorrow:
                md_parts.append(f"- **{t.title[:80]}**")
            if len(tasks_tomorrow) <= 2:
                for t in tasks_tomorrow:
                    vocal_parts.append(f"Demain : {t.title[:80]}.")
            else:
                vocal_parts.append(f"Demain, {len(tasks_tomorrow)} tâches à traiter.")

        if tasks_this_week:
            md_parts.append(f"\n**Cette semaine ({len(tasks_this_week)})**")
            for t in tasks_this_week:
                md_parts.append(f"- **{t.title[:80]}** — {_format_due(t.due_date, today)}")
            if not tasks_today and not tasks_tomorrow:
                vocal_parts.append(f"Cette semaine, {len(tasks_this_week)} tâches.")

    # ── Section 2 — Réunions ──
    if meetings_today or meetings_week:
        md_parts.append("\n### 📅 Vos réunions")
        if meetings_today:
            md_parts.append(f"\n**Aujourd'hui ({len(meetings_today)})**")
            verbe = "avez" if len(meetings_today) > 1 else "avez"
            vocal_parts.append(
                f"Vous {verbe} {len(meetings_today)} réunion{'s' if len(meetings_today) > 1 else ''} aujourd'hui."
            )
            for m in meetings_today:
                t_str = _format_time_vocal(m.scheduled_start)
                role = ""
                if getattr(m, "chair_id", None) == user.id:
                    role = " — vous présidez"
                elif getattr(m, "secretary_id", None) == user.id:
                    role = " — vous êtes secrétaire"
                md_parts.append(f"- **{m.title[:80]}** à {t_str}{role}")
                vocal_parts.append(f"{m.title[:80]} à {t_str}{role}.")
        if meetings_week:
            md_parts.append(f"\n**Cette semaine ({len(meetings_week)})**")
            for m in meetings_week:
                day = m.scheduled_start.strftime("%A %d/%m") if m.scheduled_start else ""
                md_parts.append(f"- **{m.title[:80]}** — {day}")
            if not meetings_today:
                vocal_parts.append(
                    f"Pas de réunion aujourd'hui. {len(meetings_week)} prévue{'s' if len(meetings_week) > 1 else ''} cette semaine."
                )

    # ── Section 3 — Décisions à arbitrer ──
    if my_decisions:
        md_parts.append(f"\n### ⚖ Décisions à arbitrer ({len(my_decisions)})")
        if len(my_decisions) == 1:
            vocal_parts.append("Une décision attend votre arbitrage.")
        else:
            vocal_parts.append(f"{len(my_decisions)} décisions attendent votre arbitrage.")
        for d in my_decisions[:3]:
            title = (d.title or "(sans titre)").strip()
            deadline_str = ""
            if d.deadline:
                deadline_str = f" — échéance {_format_due(d.deadline, today)}"
            prio_str = ""
            if d.priority == "critical":
                prio_str = " 🔴"
            md_parts.append(f"- **{title}**{prio_str}{deadline_str}")
            vocal_parts.append(f"{title}{deadline_str}.")

    # ── Section 4 — Sujets à surveiller ──
    if at_risk_mine:
        md_parts.append(f"\n### 🎯 Sujets à surveiller ({len(at_risk_mine)})")
        vocal_parts.append(f"{len(at_risk_mine)} sujet{'s' if len(at_risk_mine) > 1 else ''} mérite{'nt' if len(at_risk_mine) > 1 else ''} votre attention.")
        for w in at_risk_mine:
            kind_label = "Plan" if w["kind"] == "plan" else "Décision"
            title = (w.get("title") or "").strip()
            reason = (w.get("reasons", [""])[0] or "").strip()
            score = w.get("score", 0)
            md_parts.append(f"- **{title}** ({kind_label} · score {score}/100) — {reason}")
            vocal_parts.append(f"{title}. {reason}.")

    # ── Section 5 — Activité récente ──
    if recent_decisions or recent_plans:
        md_parts.append("\n### 🔔 Activité récente de l'organisation")
        if recent_decisions:
            md_parts.append("\n**Décisions récemment validées**")
            for d in recent_decisions:
                md_parts.append(f"- {d.title[:80]} ({d.status})")
        if recent_plans:
            md_parts.append("\n**Nouveaux dossiers**")
            for p in recent_plans:
                md_parts.append(f"- {p.title[:80]}")

    # ── Section 6 — Indicateurs ──
    if epi_data:
        md_parts.append("\n### 📊 Indicateurs de pilotage")
        score = epi_data.get("score", 0)
        trend = epi_data.get("trend", "")
        md_parts.append(f"\n- **EPI Score : {score}/100** {trend}")
        if epi_data.get("delta_text"):
            md_parts.append(f"- Évolution : {epi_data['delta_text']}")
        # Vocalisation discrète des KPIs (pas envahissant)
        if score > 0:
            vocal_parts.append(f"Score EPI à {score} sur 100.")

    # ── Section 7 — Équipe (manager) ──
    if team_summary and (team_summary.get("overdue", 0) > 0 or team_summary.get("active", 0) > 0):
        md_parts.append("\n### 👥 État de votre équipe")
        md_parts.append(
            f"\n- **{team_summary.get('active', 0)} tâche(s) actives**"
            f" — dont **{team_summary.get('overdue', 0)} en retard**"
        )
        if team_summary.get("top_overdue_members"):
            md_parts.append("\n**Membres ayant le plus de retards :**")
            for m in team_summary["top_overdue_members"][:3]:
                md_parts.append(f"- {m['name']} : {m['count']} en retard")
        if team_summary.get("overdue", 0) > 5:
            vocal_parts.append(
                f"Attention manager : {team_summary['overdue']} tâches en retard dans votre équipe."
            )

    # ── Closing ──
    if total_tasks > 0 or meetings_today or my_decisions:
        closing = "Bonne journée."
    else:
        closing = "Aucune urgence personnelle. Profitez-en pour avancer sur les sujets de fond. Bonne journée."
    md_parts.append(f"\n{closing}")
    vocal_parts.append(closing)

    return _assemble(md_parts, vocal_parts, tagline, {
        "my_tasks_today":     len(tasks_today),
        "my_tasks_tomorrow":  len(tasks_tomorrow),
        "my_tasks_week":      len(tasks_this_week),
        "my_tasks_overdue":   len(tasks_overdue),
        "meetings_today":     len(meetings_today),
        "meetings_week":      len(meetings_week),
        "decisions_pending":  len(my_decisions),
        "at_risk":            len(at_risk_mine),
        "recent_decisions":   len(recent_decisions),
        "recent_plans":       len(recent_plans),
        "epi_score":          epi_data.get("score") if epi_data else None,
        "team_overdue":       (team_summary or {}).get("overdue", 0) if team_summary else None,
    })


def _format_time_vocal(dt) -> str:
    """Formate une heure pour TTS français ("14 heures 30" plutôt que "14:30")."""
    if not dt:
        return ""
    h = dt.hour
    m = dt.minute
    if m == 0:
        return f"{h} heure{'s' if h > 1 else ''}"
    if m == 30:
        return f"{h} heure{'s' if h > 1 else ''} et demie"
    return f"{h} heure{'s' if h > 1 else ''} {m}"


# ─── Helpers — EPI & équipe ──────────────────────────────────────

def _load_epi_summary(*, organization) -> Optional[dict]:
    """Charge l'EPI score actuel + delta vs semaine dernière. Best-effort."""
    try:
        from apps.dashboards.services.epi_score import compute_epi_score, get_history
        current = compute_epi_score(organization=organization)
        if not current:
            return None
        history = get_history(organization=organization, days=7)
        delta_text = ""
        trend = ""
        if history and len(history) >= 2:
            delta = history[-1]["score"] - history[0]["score"]
            if delta > 2:    trend = "📈"
            elif delta < -2: trend = "📉"
            else:            trend = "➖"
            sign = "+" if delta > 0 else ""
            delta_text = f"{sign}{delta} points sur 7 jours"
        return {
            "score": current.overall_score if hasattr(current, "overall_score") else 0,
            "trend": trend,
            "delta_text": delta_text,
        }
    except Exception:  # noqa: BLE001
        logger.debug("EPI score indispo pour briefing", exc_info=True)
        return None


def _load_team_summary(*, user, organization) -> Optional[dict]:
    """Résumé de l'équipe pour un manager (head de direction)."""
    try:
        from apps.action_plans.models import ActionTask
        from apps.common.enums import ActionTaskStatus
        from apps.governance.models import Direction

        direction = Direction.objects.filter(head=user).first()
        if not direction:
            return None
        # Tâches actives des membres de la direction
        active_qs = ActionTask.unscoped.filter(
            organization=organization,
            assignee__memberships__directions=direction,
        ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])

        today = timezone.localdate()
        active = active_qs.count()
        overdue_qs = active_qs.filter(due_date__lt=today)
        overdue = overdue_qs.count()

        # Top 3 membres avec le plus de retards
        from collections import Counter
        members_with_overdue = Counter()
        for t in overdue_qs.select_related("assignee")[:50]:
            if t.assignee_id:
                name = (
                    t.assignee.get_full_name()
                    if hasattr(t.assignee, "get_full_name")
                    else t.assignee.email
                )
                members_with_overdue[name] += 1

        return {
            "direction": direction.name,
            "active": active,
            "overdue": overdue,
            "top_overdue_members": [
                {"name": name, "count": count}
                for name, count in members_with_overdue.most_common(3)
            ],
        }
    except Exception:  # noqa: BLE001
        logger.debug("Team summary indispo pour briefing", exc_info=True)
        return None


# ─── Tagline IA (best-effort, gratuit en fallback) ───────────────

def _generate_tagline(*, user_first: str, org_name: str,
                     tasks_overdue: int, tasks_today: int,
                     meetings_today: int, my_decisions: int,
                     at_risk: int) -> str:
    """Génère une phrase d'accroche contextuelle.

    Tente Claude (1 appel court, ~80 tokens). Fallback templaté déterministe
    si Claude indispo ou désactivé. Toujours non-bloquant.
    """
    # Skip LLM si désactivé en settings
    if not getattr(settings, "BRIEFING_TAGLINE_LLM_ENABLED", True):
        return _generate_tagline_fallback(tasks_overdue, tasks_today,
                                           meetings_today, my_decisions, at_risk)

    api_key = (
        getattr(settings, "ANTHROPIC_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    if not api_key:
        return _generate_tagline_fallback(tasks_overdue, tasks_today,
                                           meetings_today, my_decisions, at_risk)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Compose une phrase d'accroche personnelle (max 25 mots, sans citation, "
            f"sans préambule, ton exécutif chaleureux) pour le briefing du jour de "
            f"{user_first or 'un dirigeant'} qui gère {org_name or 'une organisation'} "
            f"et qui a aujourd'hui : "
            f"{tasks_overdue} tâche{'s' if tasks_overdue > 1 else ''} en retard, "
            f"{tasks_today} tâche{'s' if tasks_today > 1 else ''} à faire, "
            f"{meetings_today} réunion{'s' if meetings_today > 1 else ''}, "
            f"{my_decisions} décision{'s' if my_decisions > 1 else ''} à arbitrer, "
            f"{at_risk} sujet{'s' if at_risk > 1 else ''} à risque. "
            f"Pas d'emoji. Pas de salutation. Une seule phrase."
        )
        resp = client.messages.create(
            model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        if resp and resp.content:
            txt = (resp.content[0].text or "").strip().strip('"').strip()
            if 10 < len(txt) < 300:
                return txt
    except Exception:  # noqa: BLE001
        logger.debug("Claude tagline KO, fallback", exc_info=True)

    return _generate_tagline_fallback(tasks_overdue, tasks_today,
                                       meetings_today, my_decisions, at_risk)


def _generate_tagline_fallback(tasks_overdue, tasks_today, meetings_today,
                                my_decisions, at_risk) -> str:
    """Tagline déterministe sans IA, calibrée selon la charge du jour."""
    if tasks_overdue >= 3 or at_risk >= 2:
        return "Journée à reprendre en main : quelques sujets demandent un arbitrage rapide."
    if meetings_today >= 3:
        return "Agenda chargé côté réunions — pensez à protéger des plages de réflexion."
    if my_decisions >= 2:
        return "Plusieurs décisions clés à arbitrer aujourd'hui — priorisez l'impact."
    if tasks_today + tasks_tomorrow_proxy(tasks_today) >= 3:
        return "Bonne journée d'exécution en perspective. Cap sur les tâches du jour."
    if at_risk == 0 and tasks_overdue == 0 and meetings_today == 0:
        return "Aucune urgence détectée — profitez-en pour avancer sur les sujets de fond."
    return "Journée équilibrée. Avancez à votre rythme."


def tasks_tomorrow_proxy(_):
    return 0  # utilisé seulement pour lisibilité du fallback


# ─── Assemblage final ────────────────────────────────────────────

def _assemble(md_parts, vocal_parts, tagline, stats) -> dict:
    """Construit la sortie finale du briefing."""
    markdown = "\n".join(md_parts).strip()
    vocal_text = " ".join(p.strip() for p in vocal_parts if p.strip())
    vocal_text = (
        vocal_text
        .replace("…", " etc.")
        .replace("—", ",")
        .replace("**", "")
        .replace("`", "")
        # Nettoie les emojis du flux TTS (parlent mal)
        .replace("📋", "").replace("📅", "").replace("⚖", "")
        .replace("🎯", "").replace("🔔", "").replace("📊", "")
        .replace("👥", "").replace("📈", "").replace("📉", "")
        .replace("➖", "").replace("⚠", "").replace("🔴", "")
    )
    # Compact les doubles espaces issus du nettoyage emoji
    while "  " in vocal_text:
        vocal_text = vocal_text.replace("  ", " ")

    # Summary 1 phrase
    summary_parts = []
    if stats["my_tasks_overdue"]:    summary_parts.append(f"{stats['my_tasks_overdue']} en retard")
    if stats["my_tasks_today"]:      summary_parts.append(f"{stats['my_tasks_today']} aujourd'hui")
    if stats["meetings_today"]:      summary_parts.append(f"{stats['meetings_today']} réunion(s)")
    if stats["decisions_pending"]:   summary_parts.append(f"{stats['decisions_pending']} décision(s)")
    if stats["at_risk"]:              summary_parts.append(f"{stats['at_risk']} alerte(s)")
    summary = (
        "Au programme : " + ", ".join(summary_parts) + "."
        if summary_parts else "Aucune urgence détectée."
    )

    return {
        "markdown":     markdown,
        "vocal_text":   vocal_text,
        "summary":      summary,
        "tagline":      tagline or "",
        "generated_at": timezone.now().isoformat(),
        "stats":        stats,
    }
