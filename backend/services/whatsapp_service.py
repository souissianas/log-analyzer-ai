import httpx
import logging
from core.config import get_settings

logger = logging.getLogger(__name__)

async def send_whatsapp_notification(filename: str, total_errors: int, error_levels: list[str]) -> bool:
    """
    Sends a WhatsApp alert message via Twilio when critical errors are found.
    Returns True if successfully sent, False otherwise.
    """
    settings = get_settings()
    if not settings.whatsapp_enabled:
        logger.info("WhatsApp notification disabled (missing configurations in environment)")
        return False

    # Deduplicate and sort error levels for clean presentation
    unique_levels = sorted(list(set(error_levels)))
    levels_str = ", ".join(unique_levels)
    
    # Send via Twilio if Twilio configuration is present
    if settings.twilio_account_sid and settings.twilio_auth_token:
        logger.info("Sending WhatsApp notification via Twilio")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        
        body = (
            f"🚨 *Log Analyzer AI : Alerte Critique* 🚨\n\n"
            f"📁 *Fichier de log :* `{filename}`\n"
            f"💥 *Erreurs critiques détectées :* *{total_errors}*\n"
            f"🏷️ *Niveaux de gravité :* {levels_str}\n\n"
            f"⚠️ *Une intervention rapide est requise.* Veuillez consulter le tableau de bord pour plus de détails."
        )
        
        data = {
            "From": settings.twilio_from_whatsapp,
            "To": settings.twilio_to_whatsapp,
            "Body": body
        }
        
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=auth)
                if response.status_code in (200, 201):
                    logger.info("WhatsApp notification sent successfully via Twilio")
                    return True
                else:
                    logger.error(
                        "Twilio API returned error status for WhatsApp notification",
                        extra={"status_code": response.status_code, "response_body": response.text}
                    )
                    return False
        except Exception as exc:
            logger.exception("Failed to send WhatsApp notification via Twilio due to exception: %s", exc)
            return False

    return False


async def send_whatsapp_message(body: str) -> bool:
    """Sends a generic WhatsApp text message via Twilio to the configured recipient."""
    settings = get_settings()
    if not settings.whatsapp_enabled:
        logger.info("WhatsApp notification disabled (missing configurations in environment)")
        return False

    if settings.twilio_account_sid and settings.twilio_auth_token:
        logger.info("Sending generic WhatsApp message via Twilio")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        data = {
            "From": settings.twilio_from_whatsapp,
            "To": settings.twilio_to_whatsapp,
            "Body": body
        }
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=auth)
                if response.status_code in (200, 201):
                    logger.info("WhatsApp message sent successfully via Twilio")
                    return True
                else:
                    logger.error(
                        "Twilio API returned error status for WhatsApp message",
                        extra={"status_code": response.status_code, "response_body": response.text}
                    )
                    return False
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message via Twilio due to exception: %s", exc)
            return False
    return False
