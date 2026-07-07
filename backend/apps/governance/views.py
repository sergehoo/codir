"""DRF viewsets — governance (Direction).

Endpoint read-only pour peupler les sélecteurs des formulaires côté frontend
(sélection filiale + direction lors de la création d'une décision / d'un plan).
"""
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsOrganizationMember

from .models import Direction


class DirectionMiniSerializer(serializers.ModelSerializer):
    subsidiary_name = serializers.CharField(
        source="subsidiary.name", read_only=True, allow_null=True,
    )

    class Meta:
        model = Direction
        fields = ("id", "name", "code", "color", "subsidiary", "subsidiary_name")


class DirectionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /governance/directions/ — liste des directions de l'org courante.

    Filtrable par filiale via `?subsidiary=<uuid>` pour peupler des selects
    dépendants (Filiale → Direction) dans les formulaires.
    """
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    serializer_class = DirectionMiniSerializer

    def get_queryset(self):
        qs = Direction.objects.all()
        org = getattr(self.request, "organization", None)
        if org is not None:
            qs = qs.filter(organization=org)
        subsidiary = self.request.query_params.get("subsidiary")
        if subsidiary:
            qs = qs.filter(subsidiary_id=subsidiary)
        return qs.order_by("name")
