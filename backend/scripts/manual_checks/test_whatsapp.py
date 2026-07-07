import asyncio
import os
import sys

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.whatsapp_service import send_whatsapp_notification
from core.config import get_settings

async def main():
    print("=== Test de Notification WhatsApp (Log Analyzer AI) ===")
    
    settings = get_settings()
    
    print(f"WhatsApp active : {settings.whatsapp_enabled}")
    print(f"Twilio Account SID : {settings.twilio_account_sid}")
    print(f"Twilio From Number : {settings.twilio_from_whatsapp}")
    print(f"Twilio To Number   : {settings.twilio_to_whatsapp}")
    
    if not settings.whatsapp_enabled:
        print("\n[ATTENTION] La configuration WhatsApp est incomplete dans l'environnement.")
        print("\nPour tester Twilio, definissez :")
        print('  $env:TWILIO_ACCOUNT_SID="AC..."')
        print('  $env:TWILIO_AUTH_TOKEN="token"')
        print('  $env:TWILIO_FROM_WHATSAPP="whatsapp:+14155238886"')
        print('  $env:TWILIO_TO_WHATSAPP="whatsapp:+21651627025"')
        print("\nTentative d'envoi ignoree (configuration desactivee).")
        return

    print("\nEnvoi d'un message de test WhatsApp en cours...")
    success = await send_whatsapp_notification(
        filename="test_execution_whatsapp.log",
        total_errors=3,
        error_levels=["FATAL", "ERROR", "CRITICAL"]
    )
    
    if success:
        print("\n✅ Message de test envoye avec succes !")
    else:
        print("\n❌ Echec de l'envoi du message. Verifiez les logs ci-dessus.")

if __name__ == "__main__":
    asyncio.run(main())
