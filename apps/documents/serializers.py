from rest_framework import serializers

from .models import Document, DocumentAttachment


class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "name", "file", "mime", "size_bytes",
            "is_confidential", "uploaded_by",
            "download_url", "created_at",
        ]
        read_only_fields = ("mime", "size_bytes", "uploaded_by", "download_url", "created_at")

    def get_download_url(self, obj):
        if not obj.file:
            return None
        return obj.file.url

    def create(self, validated_data):
        request = self.context.get("request")
        f = validated_data["file"]
        validated_data["mime"] = getattr(f, "content_type", "") or ""
        validated_data["size_bytes"] = getattr(f, "size", 0) or 0
        if request is not None:
            validated_data["uploaded_by"] = request.user
            validated_data["organization"] = request.organization
        return Document.unscoped.create(**validated_data)


class DocumentAttachmentSerializer(serializers.ModelSerializer):
    document_detail = DocumentSerializer(source="document", read_only=True)
    target_model = serializers.CharField(write_only=True, help_text="ex. 'meetings.Meeting'")

    class Meta:
        model = DocumentAttachment
        fields = [
            "id", "document", "document_detail",
            "target_model", "target_id", "label",
            "attached_by", "created_at",
        ]
        read_only_fields = ("attached_by", "created_at")

    def create(self, validated_data):
        from django.contrib.contenttypes.models import ContentType
        target_model = validated_data.pop("target_model")
        app_label, model = target_model.split(".")
        ct = ContentType.objects.get(app_label=app_label.lower(), model=model.lower())
        request = self.context.get("request")
        return DocumentAttachment.unscoped.create(
            organization=request.organization,
            target_type=ct,
            attached_by=request.user,
            **validated_data,
        )
