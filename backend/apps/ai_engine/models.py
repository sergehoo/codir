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


# ─── Agent IA proactif (Lot 2) ────────────────────────────────

class ProactiveAlert(TenantAwareModel):
    """Trace une alerte proactive émise par l'agent IA.

    Objectifs :
    1. **Déduplication** : ne pas resignaler le même sujet (plan/decision)
       au même user pendant `cooldown_days` (5 par défaut).
    2. **Métriques** : suivi du taux d'émission, sujets les plus signalés,
       taux d'action humaine consécutif (clic, dismiss).
    """
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="proactive_alerts",
    )
    target_kind = models.CharField(max_length=20, db_index=True)
    target_id   = models.CharField(max_length=80, db_index=True)
    reason      = models.CharField(max_length=300)
    health_score_at_emit = models.PositiveSmallIntegerField(default=0)
    ai_message = models.ForeignKey(
        AIMessage, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="proactive_alerts",
    )
    status = models.CharField(
        max_length=20,
        choices=[("emitted", "Émis"), ("read", "Lu"), ("dismissed", "Ignoré")],
        default="emitted",
    )
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Pour la dédup : "ai-je signalé ce target à ce user récemment ?"
            models.Index(fields=["user", "target_kind", "target_id", "-created_at"]),
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self):
        return f"ProactiveAlert({self.target_kind}:{self.target_id} → {self.user_id})"


# ─── Recherche sémantique universelle (Lot 3) ─────────────────

class SemanticIndex(TenantAwareModel):
    """Index sémantique cross-objets pour la recherche IA universelle.

    Permet de chercher en langage naturel à travers les décisions, plans,
    réunions, transcripts, documents en utilisant une similarité vectorielle.

    Champs clés :
      - `source_type` / `source_id` : pointer générique vers l'objet métier
      - `text_hash` : sha256 du texte indexé — skip re-indexation si inchangé
      - `embedding` : vecteur 384-dim (sentence-transformers multilingue)
      - `model_version` : permet de ré-indexer sélectivement si on change de
        modèle d'embedding

    Stockage : JSONField pour MVP. Pour migrer vers pgvector quand le volume
    grossit (>10k items), changer le champ en `pgvector.django.VectorField`
    et ajouter `CREATE INDEX ... USING ivfflat` côté SQL.
    """
    SOURCE_TYPES = [
        ("decision", "Décision"),
        ("plan", "Plan d'action"),
        ("meeting", "Réunion"),
        ("transcript", "Transcript"),
        ("document", "Document"),
    ]

    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, db_index=True)
    source_id   = models.CharField(max_length=80, db_index=True)
    # Copie locale du titre + texte pour rendu rapide (évite jointures)
    title = models.CharField(max_length=300)
    text  = models.TextField()
    text_hash = models.CharField(max_length=64, db_index=True)
    # Vecteur 384-dim (List[float]). Stocké JSON pour portabilité.
    embedding = models.JSONField(default=list, blank=True)
    # Pour invalidation : si on upgrade le modèle, ré-indexer celleux avec
    # une `model_version` différente.
    model_version = models.CharField(max_length=80, default="minilm-multi-v1")
    # URL canonique pour redirection depuis les résultats de recherche
    url = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("source_type", "source_id")]
        indexes = [
            models.Index(fields=["organization", "source_type"]),
            models.Index(fields=["organization", "model_version"]),
        ]

    def __str__(self):
        return f"SemanticIndex({self.source_type}:{self.source_id})"
