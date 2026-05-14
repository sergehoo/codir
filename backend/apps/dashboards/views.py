"""Dashboard bêta — endpoint unique consolidé."""
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

        return Response({
            "kpis": {
                "upcoming_meetings": upcoming_meetings.count(),
                "in_progress_meetings": in_progress_meetings,
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
            "recent_notifications": list(recent_notifications),
        })
