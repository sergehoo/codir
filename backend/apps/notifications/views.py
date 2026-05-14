"""ViewSets DRF — notifications, préférences, test-email, dashboard."""
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification, NotificationStatus
from .serializers import (
    NotificationPreferenceSerializer, NotificationSerializer,
)
from .services import get_or_create_preference


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        try:
            qs = Notification.objects.filter(recipient=self.request.user)
            params = self.request.query_params
            if params.get("unread") == "true":
                qs = qs.filter(seen_at__isnull=True)
            if event := params.get("event"):
                qs = qs.filter(event=event)
            if channel := params.get("channel"):
                qs = qs.filter(channel=channel)
            return qs
        except Exception:  # noqa: BLE001 — graceful si migration pas encore appliquée
            return Notification.objects.none()

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        n = self.get_object()
        n.mark_read()
        return Response(NotificationSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(seen_at__isnull=True)
        now = timezone.now()
        qs.update(seen_at=now, read_at=now, status=NotificationStatus.READ)
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        try:
            n = Notification.objects.filter(recipient=request.user, seen_at__isnull=True).count()
        except Exception:  # noqa: BLE001
            n = 0
        return Response({"unread": n})

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Résumé pour le dashboard / bell."""
        try:
            qs = Notification.objects.filter(recipient=request.user)
            unread = qs.filter(seen_at__isnull=True).count()
            last5 = list(qs.order_by("-created_at")[:5])
            return Response({
                "unread": unread,
                "total": qs.count(),
                "latest": NotificationSerializer(last5, many=True).data,
            })
        except Exception as exc:  # noqa: BLE001 — fail gracefully (migration pas encore appliquée par ex.)
            return Response(
                {"unread": 0, "total": 0, "latest": [], "error": str(exc)[:300]},
                status=200,
            )


class NotificationPreferenceViewSet(viewsets.GenericViewSet):
    """Endpoint « me » — chaque user gère ses propres préférences."""
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    def _get_or_create(self):
        return get_or_create_preference(
            self.request.user,
            organization=getattr(self.request, "organization", None),
        )

    def list(self, request):
        pref = self._get_or_create()
        return Response(NotificationPreferenceSerializer(pref).data)

    @action(detail=False, methods=["get", "patch", "put"], url_path="me")
    def me(self, request):
        pref = self._get_or_create()
        if request.method == "GET":
            return Response(NotificationPreferenceSerializer(pref).data)
        ser = NotificationPreferenceSerializer(
            pref, data=request.data, partial=(request.method == "PATCH"),
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_email(request):
    """POST /notifications/test-email/ — envoie un mail de test à l'utilisateur."""
    user = request.user
    if not user.email:
        return Response({"detail": "Pas d'adresse email pour cet utilisateur."}, status=400)
    try:
        send_mail(
            subject="[CODIR] Test d'envoi",
            message=(f"Bonjour {user.get_full_name() or user.email},\n\n"
                     "Ce message confirme la configuration SMTP de CODIR Executive.\n\n"
                     "— L'équipe CODIR"),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"Échec d'envoi : {exc}"}, status=500)
    return Response({"detail": f"Email de test envoyé à {user.email}."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """GET /dashboard/notifications-summary/ — chiffres clés pour le dashboard."""
    from datetime import timedelta
    from apps.action_plans.models import ActionTask
    from apps.action_plans.services import get_manager_branch_tasks_summary
    from apps.common.enums import ActionTaskStatus

    user = request.user
    today = timezone.localdate()
    in_3 = today + timedelta(days=3)

    notifs = Notification.objects.filter(recipient=user)
    unread = notifs.filter(seen_at__isnull=True).count()

    open_tasks = ActionTask.objects.filter(
        assignee=user,
    ).exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
    overdue = open_tasks.filter(due_date__lt=today).count()
    due_soon = open_tasks.filter(due_date__gte=today, due_date__lte=in_3).count()
    critical = open_tasks.filter(priority__in=["critical", "high"]).count()

    payload = {
        "unread_notifications": unread,
        "open_tasks": open_tasks.count(),
        "overdue_tasks": overdue,
        "due_soon_tasks": due_soon,
        "critical_tasks": critical,
    }

    # Si manager → résumé du périmètre
    from apps.governance.models import Direction
    direction = Direction.objects.filter(head=user).first()
    if direction:
        payload["manager_scope"] = {
            "direction": direction.name,
            "subsidiary": getattr(direction.subsidiary, "name", None),
        }
        payload["manager_summary"] = get_manager_branch_tasks_summary(
            manager=user, direction=direction,
        )
    else:
        m = user.memberships.filter(is_owner=True).first()
        if m:
            d = m.directions.select_related("subsidiary").first()
            sub = d.subsidiary if d else None
            payload["manager_scope"] = {"subsidiary": getattr(sub, "name", None)}
            payload["manager_summary"] = get_manager_branch_tasks_summary(
                manager=user, subsidiary=sub,
            )

    return Response(payload)
