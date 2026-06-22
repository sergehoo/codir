from rest_framework import serializers

from .models import Organization, Subsidiary


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "country", "timezone", "currency",
            "plan", "is_active",
            "primary_color", "secondary_color", "surface_color", "logo",
        ]
        read_only_fields = ("id", "slug", "plan", "is_active")


class SubsidiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subsidiary
        fields = ["id", "name", "country", "currency", "parent", "is_active"]
