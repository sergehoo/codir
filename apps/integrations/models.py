"""Apps integrations — connecteurs (SAP, M365, Power BI, etc.), webhooks."""
from django.db import models

from core.models import TenantAwareModel


class IntegrationProvider(models.TextChoices):
    M365 = "m365", "Microsoft 365"
    GOOGLE = "google", "Google Workspace"
    TEAMS = "teams", "Microsoft Teams"
    ZOOM = "zoom", "Zoom"
    SHAREPOINT = "sharepoint", "SharePoint"
    SAP = "sap", "SAP S/4HANA"
    ORACLE = "oracle", "Oracle EBS"
    SAGE = "sage", "Sage"
    ODOO = "odoo", "Odoo"
    WORKDAY = "workday", "Workday"
    POWERBI = "powerbi", "Power BI"
    TABLEAU = "tableau", "Tableau"
    YOUSIGN = "yousign", "Yousign"
    DOCUSIGN = "docusign", "DocuSign"
    WHATSAPP = "whatsapp", "WhatsApp Business"
    SLACK = "slack", "Slack"
    SERVICENOW = "servicenow", "ServiceNow"
    JIRA = "jira", "Jira"
    LINEAR = "linear", "Linear"
    CUSTOM = "custom", "Custom (Webhook + API)"


class Integration(TenantAwareModel):
    AUTH_TYPE = [
        ("oauth2", "OAuth2"),
        ("oauth2_cc", "OAuth2 client credentials"),
        ("api_key", "API Key"),
        ("basic", "Basic"),
        ("client_cert", "Client certificate"),
        ("saml", "SAML 2.0"),
    ]
    provider = models.CharField(max_length=30, choices=IntegrationProvider.choices)
    name = models.CharField(max_length=120)
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE)
    config = models.JSONField(default=dict, blank=True)
    capability_flags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        unique_together = [("organization", "provider", "name")]


class IntegrationCredential(TenantAwareModel):
    integration = models.OneToOneField(Integration, on_delete=models.CASCADE, related_name="credential")
    secret_encrypted = models.BinaryField(help_text="Chiffré via Vault transit")
    refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.CharField(max_length=400, blank=True)


class IntegrationSyncRun(TenantAwareModel):
    STATUS = [
        ("queued", "En file"), ("running", "En cours"),
        ("success", "Succès"), ("partial", "Partiel"), ("failed", "Échec"),
    ]
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="sync_runs")
    scope = models.CharField(max_length=80, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_in = models.PositiveIntegerField(default=0)
    records_out = models.PositiveIntegerField(default=0)
    errors_json = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="queued")

    class Meta:
        ordering = ["-created_at"]


class Webhook(TenantAwareModel):
    event = models.CharField(max_length=80, help_text="decision.approved / kpi.threshold.breached / …")
    target_url = models.URLField()
    secret = models.CharField(max_length=120, help_text="Pour signer HMAC sortant")
    headers = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)


class WebhookDelivery(TenantAwareModel):
    STATUS = [("queued", "En file"), ("sent", "Envoyé"), ("failed", "Échec")]
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=80)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
