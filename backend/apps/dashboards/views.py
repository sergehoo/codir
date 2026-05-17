"""Dashboard bêta — endpoint unique consolidé + EPI Score."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.action_plans.models import ActionPlan, ActionTask
from apps.common.enums import (
    ActionPlanStatus, ActionTaskStatus, DecisionStatus, MeetingStatus,
)
from apps.common.permissions import IsOrganizationMember
from apps.dashboards.services.epi_score import compute_epi_score, get_history
from apps.decisions.models import Decision
from apps.meetings.models import Meeting
from apps.notifications.models import Notification


class BetaDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        user = request.user
        now = timezone.now()
        today = timezone.localdate()
        in_30d = now + timedelta(days=30)

        # Réunions à venir
        upcoming_meetings = (
            Meeting.objects.filter(
                status__in=[MeetingStatus.SCHEDULED, MeetingStatus.IN_PROGRESS],
                scheduled_start__gte=now, scheduled_start__lte=in_30d,
            )
            .order_by("scheduled_start")[:10]
        )

        in_progress_meetings = Meeting.objects.filter(status=MeetingStatus.IN_PROGRESS).count()

        # Décisions
        pending_decisions = Decision.objects.filter(status=DecisionStatus.PROPOSED).count()
        approved_decisions = Decision.objects.filter(status=DecisionStatus.APPROVED).count()
        my_decisions = Decision.objects.filter(
            responsible=user, status__in=[DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS]
        ).count()

        # Plans / tâches
        active_plans = ActionPlan.objects.filter(
            status__in=[ActionPlanStatus.OPEN, ActionPlanStatus.IN_PROGRESS]
        ).count()
        overdue_tasks = ActionTask.objects.filter(
            due_date__lt=today,
        ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED]).count()
        my_tasks_open = ActionTask.objects.filter(
            assignee=user,
        ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED]).count()
        my_tasks_overdue = ActionTask.objects.filter(
            assignee=user, due_date__lt=today,
        ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED]).count()

        # Notifications
        recent_notifications = Notification.objects.filter(
            recipient=user,
        ).order_by("-created_at")[:5].values(
            "id", "event", "level", "title", "link_url", "seen_at", "created_at",
        )

        # ─── Top 5 décisions en attente (réelles, pas du faux) ──
        top_pending_decisions = (
            Decision.objects.filter(
                status__in=[DecisionStatus.PROPOSED, DecisionStatus.APPROVED],
            )
            .select_related("responsible", "meeting")
            .order_by("deadline", "-priority", "-created_at")[:5]
        )

        # ─── Agenda items du prochain meeting ──
        next_meeting = upcoming_meetings.first()
        agenda_items_data = []
        if next_meeting:
            try:
                agenda_items_data = list(
                    next_meeting.agenda_items.all()
                    .order_by("order")
                    .values("id", "title")[:6]
                )
            except Exception:  # noqa: BLE001
                agenda_items_data = []

        # ─── Stats agrégées globales pour l'org (cards exec) ──
        completed_meetings_30d = Meeting.objects.filter(
            status=MeetingStatus.COMPLETED,
            scheduled_start__gte=now - timedelta(days=30),
        ).count()

        return Response({
            "kpis": {
                "upcoming_meetings": upcoming_meetings.count(),
                "in_progress_meetings": in_progress_meetings,
                "completed_meetings_30d": completed_meetings_30d,
                "pending_decisions": pending_decisions,
                "approved_decisions": approved_decisions,
                "my_decisions": my_decisions,
                "active_plans": active_plans,
                "overdue_tasks": overdue_tasks,
                "my_tasks_open": my_tasks_open,
                "my_tasks_overdue": my_tasks_overdue,
            },
            "upcoming_meetings": [
                {
                    "id": str(m.id),
                    "title": m.title,
                    "scheduled_start": m.scheduled_start,
                    "scheduled_end": m.scheduled_end,
                    "status": m.status,
                    "location": m.location,
                    "video_url": m.video_url,
                } for m in upcoming_meetings
            ],
            "next_meeting_agenda": [
                {"id": str(a["id"]), "title": a["title"]} for a in agenda_items_data
            ],
            "top_pending_decisions": [
                {
                    "id": str(d.id),
                    "ref": d.ref,
                    "title": d.title,
                    "deadline": d.deadline,
                    "priority": d.priority,
                    "responsible": (
                        f"{d.responsible.first_name} {d.responsible.last_name}".strip()
                        if d.responsible else None
                    ),
                    "meeting_title": d.meeting.title if d.meeting else None,
                } for d in top_pending_decisions
            ],
            "recent_notifications": list(recent_notifications),
        })


class EpiScoreView(APIView):
    """GET /api/v1/dashboards/epi-score/

    Retourne le score EPI courant + son historique 90j.

    Query params :
      - history_days : nombre de jours à inclure (défaut 90, max 365)
      - recompute    : 'true' pour recalculer en live au lieu de lire le snapshot

    Le score est :
      - calculé en live et **non persisté** par cet endpoint (lecture pure)
      - le snapshot quotidien est créé par la tâche Celery ``snapshot_epi_score_daily``
    """
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        organization = request.organization
        history_days = min(int(request.query_params.get("history_days", 90)), 365)
        recompute = request.query_params.get("recompute", "").lower() in {"1", "true", "yes"}

        # Score live (transparent — breakdown complet)
        result = compute_epi_score(organization)

        # Historique depuis snapshots persistés
        history = get_history(organization, days=history_days)

        # Si pas de snapshot du jour OU recompute demandé, on ajoute le live à la fin
        today = timezone.localdate().isoformat()
        if not history or history[-1]["date"] != today or recompute:
            history.append({
                "date": today,
                "score": result.overall_score,
                "delta": (
                    result.overall_score - history[-1]["score"] if history else 0
                ),
            })

        return Response({
            "current": result.to_dict(),
            "history": history,
            "trend": _compute_trend(history),
        })


def _compute_trend(history: list[dict]) -> dict:
    """Retourne min/max/delta sur la période, pour la sparkline."""
    if not history:
        return {"min": 0, "max": 0, "delta": 0, "direction": "flat"}
    scores = [h["score"] for h in history]
    delta = history[-1]["score"] - history[0]["score"]
    return {
        "min": min(scores),
        "max": max(scores),
        "delta": delta,
        "direction": "up" if delta > 2 else "down" if delta < -2 else "flat",
        "first_score": history[0]["score"],
        "last_score": history[-1]["score"],
    }
