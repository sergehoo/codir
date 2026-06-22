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


# ─── Push Web (Lot 6) ────────────────────────────────────────

from rest_framework.permissions import AllowAny as _AllowAny


@api_view(["GET"])
@permission_classes([_AllowAny])
def push_vapid_public_key(request):
    """GET /api/v1/notifications/push/vapid-public-key/

    Clé publique VAPID pour PushManager.subscribe() côté navigateur.
    Accessible sans auth (anonymous-readable) car nécessaire avant la
    finalisation de l'abonnement.
    """
    from django.conf import settings as _s
    return Response({"key": getattr(_s, "VAPID_PUBLIC_KEY", "")})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_subscribe(request):
    """POST /api/v1/notifications/push/subscribe/

    Enregistre ou rafraîchit un abonnement push pour le user courant.
    Body : { endpoint, keys: { p256dh, auth } }
    """
    from .models import PushSubscription

    data = request.data or {}
    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth_key = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth_key:
        return Response(
            {"detail": "endpoint, keys.p256dh, keys.auth requis."},
            status=400,
        )

    org = getattr(request, "organization", None)
    if org is None and hasattr(request.user, "memberships"):
        m = request.user.memberships.filter(is_active=True).first()
        if m:
            org = m.organization
    if org is None:
        return Response({"detail": "Aucune organisation active."}, status=400)

    sub, created = PushSubscription.unscoped.update_or_create(
        user=request.user, endpoint=endpoint,
        defaults={
            "organization": org,
            "p256dh": p256dh,
            "auth": auth_key,
            "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:300],
            "is_active": True,
            "last_error": "",
        },
    )
    return Response(
        {"id": str(sub.id), "created": created},
        status=201 if created else 200,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_unsubscribe(request):
    """POST /api/v1/notifications/push/unsubscribe/

    Désactive l'abonnement (sans hard delete pour audit). Body : { endpoint }
    """
    from .models import PushSubscription
    endpoint = ((request.data or {}).get("endpoint") or "").strip()
    if not endpoint:
        return Response({"detail": "endpoint requis."}, status=400)
    updated = (
        PushSubscription.unscoped
        .filter(user=request.user, endpoint=endpoint)
        .update(is_active=False)
    )
    return Response({"deactivated": updated})
