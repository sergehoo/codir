from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from apps.common.permissions import IsOrganizationMember

from .models import Document, DocumentAttachment
from .serializers import DocumentAttachmentSerializer, DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Document.objects.select_related("uploaded_by").all()


class DocumentAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = DocumentAttachmentSerializer

    def get_queryset(self):
        qs = (
            DocumentAttachment.objects
            .select_related("document", "target_type", "attached_by")
            .all()
        )
        tm = self.request.query_params.get("target_model")
        tid = self.request.query_params.get("target_id")
        if tm and tid:
            from django.contrib.contenttypes.models import ContentType
            try:
                app, model = tm.split(".")
                ct = ContentType.objects.get(app_label=app.lower(), model=model.lower())
                qs = qs.filter(target_type=ct, target_id=tid)
            except (ValueError, ContentType.DoesNotExist):
                return qs.none()
        return qs
