"""Tests pour services/email_service.py."""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixture : nettoie le cache de get_settings avant et après chaque test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clear_settings_cache():
    from core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# _send_smtp_sync
# ---------------------------------------------------------------------------
def test_returns_false_when_smtp_disabled(monkeypatch):
    """Si smtp_enabled=False, retourne False sans tenter de connexion."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_SENDER", raising=False)
    from services.email_service import _send_smtp_sync
    result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")
    assert result is False


def test_sends_email_via_starttls(monkeypatch):
    """Test du chemin TLS (port 587): SMTP + STARTTLS."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SENDER", "from@example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")

    from core.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.ehlo.return_value = (250, b"OK")
        mock_server.starttls.return_value = (220, b"TLS")

        from services.email_service import _send_smtp_sync
        result = _send_smtp_sync("dest@example.com", "Test Subject", "<p>Hello</p>")

    assert result is True
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()


def test_sends_email_via_ssl(monkeypatch):
    """Test du chemin SSL direct (port 465): SMTP_SSL."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_SENDER", "from@example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")

    from core.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP_SSL") as mock_ssl_cls:
        mock_server = MagicMock()
        mock_ssl_cls.return_value = mock_server

        from services.email_service import _send_smtp_sync
        result = _send_smtp_sync("dest@example.com", "Test Subject", "<p>Hello</p>")

    assert result is True
    mock_server.sendmail.assert_called_once()


def test_returns_false_on_smtp_exception(monkeypatch):
    """Si le serveur SMTP refuse la connexion, retourne False."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SENDER", "from@example.com")

    from core.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("Connection refused")):
        from services.email_service import _send_smtp_sync
        result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")

    assert result is False


def test_sends_without_credentials_when_not_provided(monkeypatch):
    """Si SMTP_USER/SMTP_PASSWORD ne sont pas definis, pas de login()."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SENDER", "from@example.com")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    from core.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        from services.email_service import _send_smtp_sync
        result = _send_smtp_sync("dest@example.com", "Subject", "<p>body</p>")

    mock_server.login.assert_not_called()
    assert result is True


# ---------------------------------------------------------------------------
# send_email (async)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_send_email_returns_false_when_smtp_disabled(monkeypatch):
    """send_email retourne False quand SMTP est desactive."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_SENDER", raising=False)
    from services.email_service import send_email
    result = await send_email("dest@example.com", "Subject", "<p>body</p>")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_delegates_to_sync_function(monkeypatch):
    """send_email appelle _send_smtp_sync en thread."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_SENDER", "from@example.com")

    from core.config import get_settings
    get_settings.cache_clear()

    with patch("services.email_service._send_smtp_sync", return_value=True) as mock_sync:
        from services.email_service import send_email
        result = await send_email("dest@example.com", "Subject", "<p>body</p>")

    assert result is True
    mock_sync.assert_called_once_with("dest@example.com", "Subject", "<p>body</p>")
