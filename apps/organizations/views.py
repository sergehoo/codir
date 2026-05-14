from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsOrganizationMember

from .models import Organization, Subsidiary
from .serializers import OrganizationSerializer, SubsidiarySerializer


class CurrentOrgView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.organization is None:
            return Response({"detail": "Aucun tenant en contexte."}, status=400)
        return Response(OrganizationSerializer(request.organization).data)


class SubsidiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = SubsidiarySerializer

    def get_queryset(self):
        return Subsidiary.objects.all()
