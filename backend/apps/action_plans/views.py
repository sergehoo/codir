"""ViewSets DRF — action_plans."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.permissions import CanModifyActionPlan, IsOrganizationMember

from . import services
from .filters import ActionPlanFilter, ActionTaskFilter
from .models import ActionComment, ActionEvidence, ActionPlan, ActionTask
from .serializers import (
    ActionCommentSerializer, ActionEvidenceSerializer,
    ActionPlanDetailSerializer, ActionPlanListSerializer,
    ActionTaskCreateSerializer, ActionTaskDetailSerializer,
    ActionTaskListSerializer, UpdateProgressSerializer,
)


class ActionPlanViewSet(viewsets.ModelViewSet):
    """ViewSet des plans d'action.

    Permissions :
      - `IsOrganizationMember` : doit appartenir à l'org
      - `CanModifyActionPlan` : update/delete réservés à staff/exec/owner
    """
    permission_classes = [IsOrganizationMember, CanModifyActionPlan]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ActionPlanFilter
    search_fields = ["title", "description_md"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return ActionPlan.objects.select_related("owner", "decision").prefetch_related("tasks")

    def get_serializer_class(self):
        return ActionPlanListSerializer if self.action == "list" else ActionPlanDetailSerializer

    @action(detail=True, methods=["get", "post"])
    def tasks(self, request, pk=None):
        plan = self.get_object()
        if request.method == "GET":
            qs = plan.tasks.select_related("assignee").all()
            return Response(ActionTaskListSerializer(qs, many=True).data)
        # ─── Création : on vérifie l'appartenance filiale ───
        if not services.user_can_add_tasks_to_plan(request.user, plan):
            return Response(
                {"detail": "Vous ne pouvez créer des tâches que sur les plans "
                           "rattachés à votre filiale."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = ActionTaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.create_task(action_plan=plan, data=ser.validated_data)
        return Response(ActionTaskDetailSerializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        plan = self.get_object()
        if request.method == "GET":
            return Response(ActionCommentSerializer(plan.comments.all(), many=True).data)
        c = ActionComment.objects.create(
            organization=request.organization, action_plan=plan,
            author=request.user, body_md=request.data.get("body_md", ""),
        )
        return Response(ActionCommentSerializer(c).data, status=201)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Stats agrégées des plans d'action."""
        from django.db.models import Avg, Count
        from apps.common.enums import ActionPlanStatus
        qs = self.get_queryset()
        by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        avg_progress = qs.aggregate(avg=Avg("progress_percent"))["avg"] or 0
        return Response({
            "total": qs.count(),
            "by_status": by_status,
            "avg_progress": round(avg_progress, 1),
            "completed": qs.filter(status=ActionPlanStatus.COMPLETED).count(),
            "blocked": qs.filter(status=ActionPlanStatus.BLOCKED).count(),
        })


class ActionTaskViewSet(viewsets.ModelViewSet):
    """ViewSet des tâches.

    Permission unique : ``IsOrganizationMember`` — tous les membres du CODIR
    voient et modifient les mêmes tâches, sans cloisonnement par filiale.
    """
    permission_classes = [IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ActionTaskFilter
    search_fields = ["title", "description_md"]
    ordering = ["due_date"]

    def get_queryset(self):
        return (
            ActionTask.objects
            .select_related("assignee", "action_plan__decision__direction__subsidiary")
            .prefetch_related("comments", "evidence", "subtasks")
        )

    def get_serializer_class(self):
        return ActionTaskListSerializer if self.action == "list" else ActionTaskDetailSerializer

    @action(detail=True, methods=["post"], url_path="update-progress")
    def update_progress(self, request, pk=None):
        ser = UpdateProgressSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.update_progress(
            task=self.get_object(),
            progress_percent=ser.validated_data["progress_percent"],
            status=ser.validated_data.get("status") or None,
            actor=request.user,
        )
        return Response(ActionTaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Archive une tâche (= passe le statut à DONE).

        Protection : la tâche doit être à 100% de progression. Sauf staff/exec
        qui peuvent forcer via `?force=true` (ou body `{force: true}`).
        """
        task_obj = self.get_object()
        # Force réservé aux super-users / executives
        force_param = (
            str(request.query_params.get("force", "")).lower() in {"1", "true", "yes"}
            or bool(request.data.get("force"))
        )
        force = force_param and (
            request.user.is_staff or getattr(request.user, "is_executive", False)
        )
        try:
            task = services.complete_task(
                task=task_obj, actor=request.user, force=force,
            )
        except services.TaskArchiveError as e:
            return Response(
                {
                    "detail": str(e),
                    "progress_percent": task_obj.progress_percent,
                    "code": "task_not_completed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ActionTaskDetailSerializer(task).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(ActionCommentSerializer(task.comments.all(), many=True).data)
        c = ActionComment.objects.create(
            organization=request.organization, task=task,
            author=request.user, body_md=request.data.get("body_md", ""),
        )
        return Response(ActionCommentSerializer(c).data, status=201)

    @action(detail=True, methods=["get", "post"])
    def evidence(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(ActionEvidenceSerializer(task.evidence.all(), many=True).data)
        e = services.add_evidence(
            task=task,
            document_id=request.data.get("document"),
            url=request.data.get("url", ""),
            description=request.data.get("description", ""),
            submitted_by=request.user,
        )
        return Response(ActionEvidenceSerializer(e).data, status=201)

    # ─── Assignation simple (création / réassignation) ──────
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """POST /action-plans/tasks/{id}/assign/ — body: { assignee }."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assignee_id = request.data.get("assignee")
        if not assignee_id:
            return Response({"detail": "assignee requis"}, status=400)
        new_assignee = User.objects.filter(id=assignee_id).first()
        if not new_assignee:
            return Response({"detail": "Utilisateur introuvable"}, status=404)
        task = services.assign_task(
            task=self.get_object(),
            assignee=new_assignee,
            assigned_by=request.user,
        )
        return Response(ActionTaskDetailSerializer(task).data)

    # ─── Rappel manuel (push immédiat) ──────────────────────
    @action(detail=True, methods=["post"])
    def remind(self, request, pk=None):
        """POST /action-plans/tasks/{id}/remind/ — push manuel à l'assignee."""
        from django.utils import timezone
        from apps.notifications.services import notify_task_due_soon, notify_task_overdue

        task = self.get_object()
        if not task.assignee:
            return Response({"detail": "Tâche sans assigné"}, status=400)
        if task.due_date and task.due_date < timezone.localdate():
            res = notify_task_overdue(task=task)
        else:
            res = notify_task_due_soon(task=task)
        if res is None:
            return Response(
                {"detail": "Rappel déjà envoyé sur le créneau, ou désactivé par préférences."},
                status=200,
            )
        return Response(
            {"detail": "Rappel envoyé", "notification_id": str(res.id)}, status=201,
        )

    # ─── Délégation / transfert d'une tâche ─────────────────
    @action(detail=True, methods=["post"])
    def delegate(self, request, pk=None):
        """POST /api/v1/action-plans/tasks/{id}/delegate/
        Body: { assignee: <uuid>, note?: <str> }
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assignee_id = request.data.get("assignee")
        if not assignee_id:
            return Response({"detail": "assignee requis"}, status=400)
        new_assignee = User.objects.filter(id=assignee_id).first()
        if not new_assignee:
            return Response({"detail": "Utilisateur introuvable"}, status=404)
        task = services.delegate_task(
            task=self.get_object(),
            new_assignee=new_assignee,
            by_user=request.user,
            note=request.data.get("note", ""),
        )
        return Response(ActionTaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"])
    def postpone(self, request, pk=None):
        """Reporte l'échéance. Body: { due_date: 'YYYY-MM-DD', reason?: str }."""
        new_date = request.data.get("due_date")
        if not new_date:
            return Response({"detail": "due_date requis"}, status=400)
        task = services.postpone_task(
            task=self.get_object(),
            new_due_date=new_date,
            by_user=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(ActionTaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = services.cancel_task(
            task=self.get_object(),
            by_user=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(ActionTaskDetailSerializer(task).data)

    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        qs = self.get_queryset().filter(assignee=request.user).exclude(
            status__in=["done", "cancelled"]
        )
        page = self.paginate_queryset(qs)
        ser = ActionTaskListSerializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    # ─── Liste TOUTES les tâches — Live CODIR Mode ─────────────
    @action(detail=False, methods=["get"], url_path="all")
    def all_tasks(self, request):
        """GET /api/v1/action-plans/tasks/all/
        Endpoint alternatif robuste au routage : 2 segments d'URL → ne peut
        jamais entrer en conflit avec le pattern `<pk>/` du plans_router.
        Applique les mêmes filtres que la LIST (DjangoFilterBackend).
        """
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        ser = ActionTaskListSerializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    # ─── Bulk update — Live CODIR Mode ────────────────────────
    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        """POST /api/v1/action-plans/tasks/bulk-update/
        Body: {
            "task_ids": ["uuid1", "uuid2", ...],
            "updates": {
                "status": "in_progress" | "done" | "blocked" | ...,
                "due_date": "YYYY-MM-DD" | null,
                "assignee": "<user_uuid>" | null,
                "priority": "low|medium|high|critical",
                "comment": "<note libre — créera un ActionComment sur chaque task>"
            }
        }
        Tous les champs des updates sont optionnels. Bulk update atomique.
        """
        from django.contrib.auth import get_user_model
        from django.db import transaction
        from django.utils import timezone

        from apps.common.enums import ActionTaskStatus

        User = get_user_model()
        task_ids = request.data.get("task_ids", [])
        updates = request.data.get("updates", {})
        if not task_ids:
            return Response({"detail": "task_ids requis (liste non vide)"}, status=400)
        if not isinstance(updates, dict) or not updates:
            return Response({"detail": "updates requis (dict non vide)"}, status=400)

        # Validation des valeurs reçues
        allowed_statuses = {s.value for s in ActionTaskStatus}
        if "status" in updates and updates["status"] not in allowed_statuses:
            return Response(
                {"detail": f"status invalide ({updates['status']})"}, status=400,
            )

        new_assignee = None
        if updates.get("assignee"):
            new_assignee = User.objects.filter(id=updates["assignee"]).first()
            if not new_assignee:
                return Response({"detail": "assignee introuvable"}, status=404)

        qs = self.get_queryset().filter(id__in=task_ids)
        if not qs.exists():
            return Response({"detail": "aucune tâche trouvée"}, status=404)

        # Pas de cloisonnement par filiale : tous les membres CODIR peuvent
        # modifier toutes les tâches de l'organisation.

        comment_text = (updates.get("comment") or "").strip()
        updated_count = 0
        with transaction.atomic():
            for task in qs:
                changed = []
                if "status" in updates:
                    task.status = updates["status"]
                    changed.append("status")
                    # Si on passe à done sans completed_at, on le set
                    if updates["status"] == ActionTaskStatus.DONE and not task.completed_at:
                        task.completed_at = timezone.now()
                        changed.append("completed_at")
                if "due_date" in updates:
                    task.due_date = updates["due_date"] or None
                    changed.append("due_date")
                if new_assignee is not None:
                    task.assignee = new_assignee
                    changed.append("assignee")
                if "priority" in updates:
                    task.priority = updates["priority"]
                    changed.append("priority")
                if changed:
                    task.save(update_fields=changed + ["updated_at"])
                    updated_count += 1
                if comment_text:
                    ActionComment.objects.create(
                        organization=request.organization,
                        task=task,
                        author=request.user,
                        body_md=comment_text,
                    )

        return Response({
            "updated": updated_count,
            "total_requested": len(task_ids),
            "applied": list(updates.keys()),
        })

    # ─── Stats ────────────────────────────────────────────
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Agrégats tasks : par statut, par priorité, retards, échéances proches."""
        from datetime import timedelta
        from django.db.models import Count
        from django.utils import timezone
        from apps.common.enums import ActionTaskStatus
        today = timezone.localdate()
        in_7_days = today + timedelta(days=7)
        qs = self.get_queryset()
        by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        by_priority = dict(qs.values("priority").annotate(c=Count("id")).values_list("priority", "c"))
        return Response({
            "total": qs.count(),
            "by_status": by_status,
            "by_priority": by_priority,
            "overdue": qs.filter(due_date__lt=today)
                        .exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
                        .count(),
            "done": qs.filter(status=ActionTaskStatus.DONE).count(),
            "due_this_week": qs.filter(due_date__gte=today, due_date__lte=in_7_days)
                               .exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
                               .count(),
            "unassigned": qs.filter(assignee__isnull=True).count(),
        })
