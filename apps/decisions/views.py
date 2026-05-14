"""ViewSets DRF — decisions."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.action_plans.serializers import ActionPlanDetailSerializer
from apps.common.permissions import IsOrganizationMember

from . import services
from .filters import DecisionFilter
from .models import Decision, DecisionCategory, DecisionComment, DecisionHistory
from .serializers import (
    ApproveDecisionSerializer, ConvertToActionPlanSerializer,
    DecisionCategorySerializer, DecisionCommentSerializer,
    DecisionCreateSerializer, DecisionDetailSerializer,
    DecisionHistorySerializer, DecisionListSerializer,
)


class DecisionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DecisionFilter
    search_fields = ["ref", "title", "description_md"]
    ordering_fields = ["created_at", "deadline", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Decision.objects
            .select_related("responsible", "approved_by", "category", "direction",
                            "meeting", "agenda_item")
            .prefetch_related("history", "comments")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return DecisionListSerializer
        if self.action == "create":
            return DecisionCreateSerializer
        return DecisionDetailSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = services.create_decision(
            organization=request.organization,
            created_by=request.user,
            data=ser.validated_data,
        )
        return Response(DecisionDetailSerializer(d).data, status=status.HTTP_201_CREATED)

    # ─── Transitions ───────────────────────────────────────────
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        d = services.approve_decision(decision=self.get_object(), approver=request.user)
        return Response(DecisionDetailSerializer(d).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        d = services.start_decision(decision=self.get_object(), actor=request.user)
        return Response(DecisionDetailSerializer(d).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        d = services.complete_decision(decision=self.get_object(), actor=request.user)
        return Response(DecisionDetailSerializer(d).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        d = services.cancel_decision(
            decision=self.get_object(), actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(DecisionDetailSerializer(d).data)

    @action(detail=True, methods=["post"], url_path="convert-to-action-plan")
    def convert_to_action_plan(self, request, pk=None):
        ser = ConvertToActionPlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        plan = services.convert_to_action_plan(
            decision=self.get_object(), actor=request.user, **ser.validated_data,
        )
        return Response(ActionPlanDetailSerializer(plan).data, status=201)

    # ─── Sous-ressources ──────────────────────────────────────
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        d = self.get_object()
        return Response(DecisionHistorySerializer(d.history.all(), many=True).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        d = self.get_object()
        if request.method == "GET":
            return Response(DecisionCommentSerializer(d.comments.all(), many=True).data)
        ser = DecisionCommentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        c = DecisionComment.objects.create(
            organization=request.organization, decision=d, author=request.user,
            body_md=ser.validated_data["body_md"],
        )
        return Response(DecisionCommentSerializer(c).data, status=201)

    # ─── Vues filtrées spéciales ─────────────────────────────
    @action(detail=False, methods=["get"], url_path="my-decisions")
    def my_decisions(self, request):
        qs = self.get_queryset().filter(responsible=request.user)
        page = self.paginate_queryset(qs)
        ser = DecisionListSerializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Stats agrégées des décisions du tenant."""
        from django.db.models import Count
        from django.utils import timezone
        from apps.common.enums import DecisionStatus
        today = timezone.localdate()
        qs = self.get_queryset()
        by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        by_priority = dict(qs.values("priority").annotate(c=Count("id")).values_list("priority", "c"))
        by_impact = dict(qs.values("impact").annotate(c=Count("id")).values_list("impact", "c"))
        active_statuses = [DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS, DecisionStatus.PROPOSED]
        return Response({
            "total": qs.count(),
            "by_status": by_status,
            "by_priority": by_priority,
            "by_impact": by_impact,
            "overdue": qs.filter(deadline__lt=today, status__in=active_statuses).count(),
            "approved": qs.filter(status=DecisionStatus.APPROVED).count(),
            "completed": qs.filter(status=DecisionStatus.COMPLETED).count(),
            "pending": qs.filter(status=DecisionStatus.PROPOSED).count(),
            "confidential": qs.filter(is_confidential=True).count(),
        })

    @action(detail=True, methods=["post"])
    def postpone(self, request, pk=None):
        """Reporte une décision avec nouvelle échéance.
        Body: { deadline?: 'YYYY-MM-DD' }
        """
        from datetime import date
        from . import services
        new_deadline = request.data.get("deadline")
        parsed = date.fromisoformat(new_deadline) if new_deadline else None
        d = services.postpone_decision(decision=self.get_object(), actor=request.user, new_deadline=parsed)
        return Response(DecisionDetailSerializer(d).data)


class DecisionCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = DecisionCategorySerializer

    def get_queryset(self):
        return DecisionCategory.objects.all()
