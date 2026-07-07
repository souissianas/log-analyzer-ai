import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from core.config import get_settings

logger = logging.getLogger(__name__)


def _send_smtp_sync(recipient: str, subject: str, html_content: str) -> bool:
    """Envoi synchrone d'un email en utilisant la configuration SMTP."""
    settings = get_settings()
    if not settings.smtp_enabled:
        logger.warning("SMTP non configuré ou désactivé.")
        return False

    msg = MIMEText(html_content, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_sender
    msg["To"] = recipient

    try:
        # TLS (normalement sur le port 587) ou SSL (normalement sur le port 465) ou pas de chiffrement (port 25)
        use_ssl = settings.smtp_port == 465

        if use_ssl:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)

        # Si ce n'est pas SSL direct, on initie STARTTLS si supporté
        if not use_ssl:
            try:
                server.ehlo()
                server.starttls()
                server.ehlo()
            except Exception as e:
                logger.info(f"STARTTLS non disponible ou a échoué: {e}")

        # Authentification si credentials fournis
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)

        server.sendmail(settings.smtp_sender, [recipient], msg.as_string())
        server.quit()
        logger.info(f"Email envoyé avec succès à {recipient}")
        return True
    except Exception as exc:
        logger.exception(f"Erreur d'envoi d'email SMTP à {recipient}: {exc}")
        return False


async def send_email(recipient: str, subject: str, html_content: str) -> bool:
    """Envoi asynchrone d'un email en arrière-plan."""
    settings = get_settings()
    if not settings.smtp_enabled:
        logger.info("Service email SMTP désactivé.")
        return False
    return await asyncio.to_thread(_send_smtp_sync, recipient, subject, html_content)
