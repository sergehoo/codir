"""Diagnostic SMTP — envoie un mail de test direct (court-circuite Celery).

Usage :
    python manage.py test_email --to user@example.com
    python manage.py test_email --to user@example.com --verbose

Affiche aussi la config courante pour vérifier qu'on cible le bon SMTP.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un email de test pour valider la config SMTP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", required=True,
            help="Adresse email destinataire (obligatoire).",
        )
        parser.add_argument(
            "--subject", default="[CODIR] Test SMTP",
            help="Sujet du mail de test.",
        )
        parser.add_argument(
            "--verbose", action="store_true",
            help="Affiche les headers et la réponse SMTP brute.",
        )

    def handle(self, *args, **opts):
        to_addr: str = opts["to"]
        subject: str = opts["subject"]
        verbose: bool = opts["verbose"]

        # 1) Affiche la config
        self.stdout.write(self.style.NOTICE("─── Config SMTP active ───"))
        for key in (
            "EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT",
            "EMAIL_HOST_USER", "EMAIL_USE_TLS", "EMAIL_USE_SSL",
            "DEFAULT_FROM_EMAIL", "EMAIL_REPLY_TO", "SERVER_EMAIL",
            "FRONTEND_BASE_URL",
        ):
            val = getattr(settings, key, "<absent>")
            # Masque le password si jamais demandé
            self.stdout.write(f"  {key} = {val}")
        # Affiche si password est défini (sans le révéler)
        has_pw = bool(getattr(settings, "EMAIL_HOST_PASSWORD", ""))
        self.stdout.write(f"  EMAIL_HOST_PASSWORD = {'(défini)' if has_pw else '(VIDE)'}")
        self.stdout.write("")

        # 2) Construit le message
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        reply_to = (
            getattr(settings, "EMAIL_REPLY_TO", None)
            or getattr(settings, "SERVER_EMAIL", None)
        )

        body_text = (
            "Bonjour,\n\n"
            "Ceci est un test de la configuration SMTP de CODIR.\n"
            f"Envoyé depuis : {getattr(settings, 'EMAIL_HOST', '?')}\n"
            f"Destinataire : {to_addr}\n\n"
            "Si vous lisez ce message, le SMTP fonctionne. Vérifiez aussi le\n"
            "dossier Spam de votre boîte si le mail manque dans la boîte de\n"
            "réception principale.\n\n"
            "--\nCODIR Executive Platform"
        )
        body_html = f"""
<html><body style="font-family:system-ui,sans-serif;padding:20px;color:#222;">
  <h2 style="color:#b65a0c;">Test SMTP CODIR</h2>
  <p>Bonjour,</p>
  <p>Ceci est un test de la configuration SMTP de CODIR.</p>
  <ul>
    <li>Hôte : <code>{getattr(settings, 'EMAIL_HOST', '?')}</code></li>
    <li>Destinataire : <code>{to_addr}</code></li>
    <li>From : <code>{from_email}</code></li>
  </ul>
  <p>Si vous lisez ce message, l'envoi SMTP fonctionne.</p>
  <hr><small>CODIR Executive Platform — diagnostic email</small>
</body></html>
"""

        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_email,
            to=[to_addr],
            reply_to=[reply_to] if reply_to else None,
        )
        msg.attach_alternative(body_html, "text/html")

        # 3) Headers transactionnels (mêmes que la prod)
        site_url = getattr(settings, "FRONTEND_BASE_URL", "https://codir.local")
        raw_from = (from_email or "").split("<")[-1].rstrip(">")
        domain = raw_from.rsplit("@", 1)[-1] if "@" in raw_from else "codir.local"
        msg.extra_headers = {
            "Message-ID": f"<codir-test-{to_addr.replace('@', '-')}@{domain}>",
            "List-Unsubscribe": f"<{site_url.rstrip('/')}/notifications/preferences>",
            "X-Test-Email": "codir-diagnostic",
        }

        if verbose:
            self.stdout.write(self.style.NOTICE("─── Headers envoyés ───"))
            self.stdout.write(f"  Subject: {subject}")
            self.stdout.write(f"  From:    {from_email}")
            self.stdout.write(f"  To:      {to_addr}")
            self.stdout.write(f"  Reply-To: {reply_to or '(none)'}")
            for k, v in msg.extra_headers.items():
                self.stdout.write(f"  {k}: {v}")
            self.stdout.write("")

        # 4) Envoi avec connexion explicite pour capturer les erreurs nettement
        self.stdout.write(self.style.NOTICE("─── Envoi en cours… ───"))
        try:
            conn = get_connection(fail_silently=False)
            sent = conn.send_messages([msg])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"ÉCHEC SMTP : {exc}") from exc

        if sent:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Message accepté par le serveur SMTP "
                f"({sent} message{'s' if sent > 1 else ''}).",
            ))
            self.stdout.write(
                "Note : "
                "« accepté » ≠ « livré dans Inbox ». Vérifiez le destinataire, "
                "y compris le dossier Spam / Promotions. Si rien n'arrive, "
                "auditez SPF/DKIM/DMARC du domaine émetteur sur mail-tester.com.",
            )
        else:
            raise CommandError("Le serveur SMTP a refusé le message (0 envoyé).")
