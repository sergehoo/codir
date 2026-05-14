"""Apps search — meta-index, suggestions, recherches enregistrées."""
from django.db import models

from core.models import TenantAwareModel


class SearchSuggestion(TenantAwareModel):
    """Suggestions de typeahead à partir des requêtes fréquentes."""

    text = models.CharField(max_length=200, db_index=True)
    hit_count = models.PositiveIntegerField(default=1)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("organization", "text")]


class SavedSearch(TenantAwareModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="saved_searches")
    name = models.CharField(max_length=120)
    query = models.JSONField(default=dict, blank=True)
    is_alert = models.BooleanField(default=False)
    alert_frequency = models.CharField(max_length=20, default="daily", blank=True)


class SearchIndexConfig(TenantAwareModel):
    """Mapping logique : quel modèle est indexé dans quel index OpenSearch."""

    model_label = models.CharField(max_length=80)  # ex. decisions.Decision
    opensearch_index = models.CharField(max_length=120)
    mapping_version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
