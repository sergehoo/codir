"""Apps ai_engine — copilot, RAG, journal d'inférence, glossaire tenant."""
from django.db import models

from core.models import TenantAwareModel


class AIConversation(TenantAwareModel):
    SCOPE = [
        ("org", "Organisation"),
        ("meeting", "Réunion"),
        ("decision", "Décision"),
        ("dashboard", "Dashboard"),
        ("document", "Document"),
    ]
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=200, blank=True)
    context_scope = models.CharField(max_length=20, choices=SCOPE, default="org")
    context_id = models.CharField(max_length=80, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]


class AIMessage(TenantAwareModel):
    ROLE = [("user", "Utilisateur"), ("assistant", "Assistant"), ("system", "Système"), ("tool", "Outil")]
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE)
    content_md = models.TextField()
    tokens = models.PositiveIntegerField(default=0)
    citations_json = models.JSONField(default=list, blank=True)
    tool_calls_json = models.JSONField(default=list, blank=True)
    feedback = models.SmallIntegerField(null=True, blank=True, help_text="+1 / -1 user feedback")

    class Meta:
        ordering = ["created_at"]


class AIInferenceLog(TenantAwareModel):
    """Journal immuable de chaque inférence IA (audit + observabilité)."""

    capability = models.CharField(max_length=40)
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=80)
    actor = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    request_hash = models.CharField(max_length=64, db_index=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    cached = models.BooleanField(default=False)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    risk_class = models.CharField(max_length=20, default="low", help_text="AI Act classification")

    class Meta:
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["capability", "provider"]),
        ]


class AIDocumentEmbedding(TenantAwareModel):
    """Embeddings vectoriels d'un chunk de document — pour RAG."""

    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="embeddings")
    chunk_index = models.PositiveIntegerField()
    content_text = models.TextField()
    language = models.CharField(max_length=10, default="fr")
    # Pour MVP on stocke en JSONField ; on switch en pgvector via SQL migration en prod.
    embedding = models.JSONField()
    model_version = models.CharField(max_length=80)

    class Meta:
        unique_together = [("document", "chunk_index")]
        indexes = [
            models.Index(fields=["organization", "document"]),
            models.Index(fields=["organization", "language"]),
        ]


class AIGlossary(TenantAwareModel):
    term = models.CharField(max_length=120)
    definition = models.TextField()
    aliases = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=40, blank=True)
    added_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("organization", "term")]
        ordering = ["term"]


# ─── AIActionRequest : action proposée par l'IA, en attente confirmation ──

class AIActionRequest(TenantAwareModel):
    """Demande d'action générée par l'IA dans une conversation, en attente
    de validation utilisateur.

    Workflow :
      1. L'IA détecte une intention d'action (ex: "Crée une tâche pour le DAF")
      2. Elle propose la création via JSON structuré dans sa réponse
      3. Le backend parse → crée un AIActionRequest(status=PENDING)
      4. Le frontend affiche une carte de confirmation
      5. L'user confirme → AIActionExecution + objet créé en DB
      6. L'user annule → status=CANCELLED, log conservé pour audit

    Le payload stocke les paramètres exacts (titre, responsable, échéance, ...)
    nécessaires pour exécuter l'action.
    """

    ACTION_TYPES = [
        ("create_decision_draft", "Créer un brouillon de décision"),
        ("create_action_task",    "Créer une tâche"),
        ("create_action_plan",    "Créer un plan d'action"),
        ("assign_task",           "Réassigner une tâche"),
        ("update_task_status",    "Changer le statut d'une tâche"),
        ("send_notification",     "Envoyer une notification"),
    ]

    STATUS = [
        ("pending",   "En attente confirmation"),
        ("confirmed", "Confirmée par l'utilisateur"),
        ("executed",  "Exécutée"),
        ("cancelled", "Annulée"),
        ("failed",    "Échec d'exécution"),
    ]

    conversation = models.ForeignKey(
        AIConversation, on_delete=models.CASCADE, related_name="action_requests",
    )
    # Le message assistant qui a généré cette proposition (pour traçabilité)
    source_message = models.ForeignKey(
        AIMessage, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="action_requests",
    )
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="ai_actions_proposed_to",
    )
    action_type = models.CharField(max_length=40, choices=ACTION_TYPES, db_index=True)
    # Paramètres validés pour exécuter l'action (titre, responsable, échéance...)
    payload = models.JSONField(default=dict, blank=True)
    # Texte humain qui explique l'action pour l'UI de confirmation
    summary = models.CharField(max_length=400, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS, default="pending", db_index=True,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    executed_at  = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    # ID de l'objet créé dans le module cible (Decision/ActionTask/etc.) pour
    # qu'on puisse linker depuis l'UI après exécution.
    result_object_type = models.CharField(max_length=60, blank=True)
    result_object_id   = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "status"]),
            models.Index(fields=["requested_by", "status"]),
        ]

    def __str__(self):
        return f"AIAction({self.action_type}, {self.status})"
