"""ViewSets DRF — agendas."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import IsOrganizationMember

from . import services
from .models import Agenda, AgendaItem, AgendaItemComment
from .serializers import (
    AgendaItemCommentSerializer, AgendaItemSerializer,
    AgendaSerializer, DiscussItemSerializer,
    PostponeItemSerializer, ReorderItemsSerializer,
)


class AgendaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = AgendaSerializer

    def get_queryset(self):
        return Agenda.objects.select_related("meeting", "validated_by").prefetch_related("items")

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        agenda = self.get_object()
        agenda = services.validate_agenda(agenda=agenda, validator=request.user)
        return Response(AgendaSerializer(agenda).data)

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        agenda = self.get_object()
        ser = ReorderItemsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.reorder_items(agenda=agenda, ordered_ids=ser.validated_data["ordered_ids"])
        return Response(AgendaSerializer(agenda).data)

    @action(detail=True, methods=["get", "post"])
    def items(self, request, pk=None):
        agenda = self.get_object()
        if request.method == "GET":
            return Response(AgendaItemSerializer(agenda.items.all(), many=True).data)
        ser = AgendaItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = services.add_item(agenda=agenda, data=ser.validated_data, created_by=request.user)
        return Response(AgendaItemSerializer(item).data, status=status.HTTP_201_CREATED)


class AgendaItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = AgendaItemSerializer

    def get_queryset(self):
        return (
            AgendaItem.objects
            .select_related("responsible", "agenda__meeting")
            .prefetch_related("comments")
        )

    @action(detail=True, methods=["post"])
    def discuss(self, request, pk=None):
        item = self.get_object()
        ser = DiscussItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = services.discuss_item(item=item, notes_md=ser.validated_data.get("notes_md", ""), actor=request.user)
        return Response(AgendaItemSerializer(item).data)

    @action(detail=True, methods=["post"])
    def postpone(self, request, pk=None):
        item = self.get_object()
        ser = PostponeItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = services.postpone_item(item=item, reason=ser.validated_data.get("reason", ""), actor=request.user)
        return Response(AgendaItemSerializer(item).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        item = self.get_object()
        if request.method == "GET":
            return Response(AgendaItemCommentSerializer(item.comments.all(), many=True).data)
        ser = AgendaItemCommentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        c = AgendaItemComment.objects.create(
            organization=request.organization, item=item,
            author=request.user, body_md=ser.validated_data["body_md"],
        )
        return Response(AgendaItemCommentSerializer(c).data, status=201)
