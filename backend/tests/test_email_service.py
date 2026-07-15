"""Tests pour services/email_service.py."""
import os
import unittest
from unittest.mock import MagicMock, patch, call

os.environ.pop("DATABASE_URL", None)
os.environ.pop("SQLITE_DB_PATH", None)


class TestSendSmtpSync(unittest.TestCase):

    def setUp(self):
        from core.config import get_settings
        get_settings.cache_clear()

    def tearDown(self):
        from core.config import get_settings
        get_settings.cache_clear()
        for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_SENDER", "SMTP_USER", "SMTP_PASSWORD"):
            os.environ.pop(key, None)

    def test_returns_false_when_smtp_disabled(self):
        """Si smtp_enabled=False, retourne False sans tenter de connexion."""
        os.environ.pop("SMTP_HOST", None)
        os.environ.pop("SMTP_SENDER", None)
        from services.email_service import _send_smtp_sync
        result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")
        self.assertFalse(result)

    def test_sends_email_via_starttls(self):
        """Test du chemin TLS (port 587): SMTP + STARTTLS."""
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_SENDER"] = "from@example.com"
        os.environ["SMTP_USER"] = "user"
        os.environ["SMTP_PASSWORD"] = "pass"

        from core.config import get_settings
        get_settings.cache_clear()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server
            mock_server.ehlo.return_value = (250, b"OK")
            mock_server.starttls.return_value = (220, b"TLS")

            from services.email_service import _send_smtp_sync
            result = _send_smtp_sync("dest@example.com", "Test Subject", "<p>Hello</p>")

        self.assertTrue(result)
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_sends_email_via_ssl(self):
        """Test du chemin SSL direct (port 465): SMTP_SSL."""
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_PORT"] = "465"
        os.environ["SMTP_SENDER"] = "from@example.com"
        os.environ["SMTP_USER"] = "user"
        os.environ["SMTP_PASSWORD"] = "pass"

        from core.config import get_settings
        get_settings.cache_clear()

        with patch("smtplib.SMTP_SSL") as mock_ssl_cls:
            mock_server = MagicMock()
            mock_ssl_cls.return_value = mock_server

            from services.email_service import _send_smtp_sync
            result = _send_smtp_sync("dest@example.com", "Test Subject", "<p>Hello</p>")

        self.assertTrue(result)
        mock_server.sendmail.assert_called_once()

    def test_returns_false_on_smtp_exception(self):
        """Si le serveur SMTP refuse la connexion, retourne False."""
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_SENDER"] = "from@example.com"

        from core.config import get_settings
        get_settings.cache_clear()

        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("Connection refused")):
            from services.email_service import _send_smtp_sync
            result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")

        self.assertFalse(result)

    def test_sends_without_credentials_when_not_provided(self):
        """Si SMTP_USER/SMTP_PASSWORD ne sont pas definis, pas de login()."""
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_SENDER"] = "from@example.com"
        os.environ.pop("SMTP_USER", None)
        os.environ.pop("SMTP_PASSWORD", None)

        from core.config import get_settings
        get_settings.cache_clear()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            from services.email_service import _send_smtp_sync
            result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")

        mock_server.login.assert_not_called()
        self.assertTrue(result)


class TestSendEmailAsync(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        from core.config import get_settings
        get_settings.cache_clear()

    def tearDown(self):
        from core.config import get_settings
        get_settings.cache_clear()
        for key in ("SMTP_HOST", "SMTP_SENDER"):
            os.environ.pop(key, None)

    async def test_returns_false_when_smtp_disabled(self):
        """send_email retourne False quand SMTP est desactive."""
        os.environ.pop("SMTP_HOST", None)
        os.environ.pop("SMTP_SENDER", None)
        from services.email_service import send_email
        result = await send_email("dest@example.com", "Subject", "<p>body</p>")
        self.assertFalse(result)

    async def test_delegates_to_sync_function(self):
        """send_email appelle _send_smtp_sync en thread."""
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_SENDER"] = "from@example.com"

        from core.config import get_settings
        get_settings.cache_clear()

        with patch("services.email_service._send_smtp_sync", return_value=True) as mock_sync:
            from services.email_service import send_email
            result = await send_email("dest@example.com", "Subject", "<p>body</p>")

        self.assertTrue(result)
        mock_sync.assert_called_once_with("dest@example.com", "Subject", "<p>body</p>")


if __name__ == "__main__":
    unittest.main()
