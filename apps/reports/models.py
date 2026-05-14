"""Apps reports — templates de rapport, runs, rapports planifiés."""
from django.db import models

from core.models import TenantAwareModel


class ReportTemplate(TenantAwareModel):
    FORMAT = [("docx", "Word"), ("xlsx", "Excel"), ("pdf", "PDF"), ("pptx", "PowerPoint")]

    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    format = models.CharField(max_length=10, choices=FORMAT, default="pdf")
    spec = models.JSONField(default=dict, blank=True)
    template_file = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = [("organization", "code")]


class ReportRun(TenantAwareModel):
    STATUS = [
        ("queued", "En file"), ("running", "En cours"),
        ("completed", "Terminé"), ("failed", "Échec"),
    ]
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name="runs")
    parameters = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    output_file = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="report_runs_output")
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class ScheduledReport(TenantAwareModel):
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name="schedules")
    cron = models.CharField(max_length=80)
    timezone = models.CharField(max_length=50, default="Europe/Paris")
    parameters = models.JSONField(default=dict, blank=True)
    recipients = models.ManyToManyField("accounts.User", blank=True, related_name="scheduled_reports")
    recipient_emails = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
