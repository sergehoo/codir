from django_filters import rest_framework as filters

from .models import Meeting


class MeetingFilter(filters.FilterSet):
    """Filtres URL pour /api/v1/meetings/.

    NB : `from_date`, `to_date`, `type` sont des filtres custom (pas des champs
    modèle). Les inclure dans `Meta.fields` planterait django-filter à
    l'initialisation (tentative de résolution comme champs Meeting). On ne met
    dans `Meta.fields` que les vrais noms de champs modèle ; les filtres custom
    sont automatiquement actifs par leur déclaration.
    """

    status = filters.CharFilter(field_name="status")
    chair = filters.UUIDFilter(field_name="chair_id")
    secretary = filters.UUIDFilter(field_name="secretary_id")
    from_date = filters.DateTimeFilter(field_name="scheduled_start", lookup_expr="gte")
    to_date = filters.DateTimeFilter(field_name="scheduled_start", lookup_expr="lte")
    type = filters.CharFilter(field_name="meeting_type")

    class Meta:
        model = Meeting
        fields: list[str] = []
