"""Lot 6 — PWA + Web Push : stockage des abonnements navigateur."""
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_proactive_agent_pref"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("endpoint", models.URLField(db_index=True, max_length=600)),
                ("p256dh", models.CharField(max_length=160)),
                ("auth", models.CharField(max_length=80)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("is_active", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=200)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="push_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="pushsubscription",
            constraint=models.UniqueConstraint(
                fields=["user", "endpoint"], name="uniq_user_endpoint",
            ),
        ),
        migrations.AddIndex(
            model_name="pushsubscription",
            index=models.Index(fields=["user", "is_active"], name="notif_pushsub_user_act_idx"),
        ),
    ]
