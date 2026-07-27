"""Tests pour core/config.py — toutes les proprietes de Settings."""
import warnings
import pytest


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
# api_key / auth_enabled
# ---------------------------------------------------------------------------
def test_api_key_returns_none_when_not_set(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.api_key is None


def test_api_key_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "my-secret")
    from core.config import Settings
    s = Settings()
    assert s.api_key == "my-secret"


def test_auth_disabled_when_no_api_key(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.auth_enabled is False


def test_auth_enabled_when_api_key_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "some-key")
    from core.config import Settings
    s = Settings()
    assert s.auth_enabled is True


# ---------------------------------------------------------------------------
# cors_origins
# ---------------------------------------------------------------------------
def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    from core.config import Settings
    s = Settings()
    origins = s.cors_origins
    assert isinstance(origins, list)
    assert len(origins) > 0


def test_cors_origins_custom(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://app.example.com,https://admin.example.com")
    from core.config import Settings
    s = Settings()
    assert s.cors_origins == ["http://app.example.com", "https://admin.example.com"]


def test_cors_origins_strips_whitespace(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "  http://a.com , http://b.com  ")
    from core.config import Settings
    s = Settings()
    assert "http://a.com" in s.cors_origins
    assert "http://b.com" in s.cors_origins


# ---------------------------------------------------------------------------
# jwt_secret_key
# ---------------------------------------------------------------------------
def test_jwt_secret_returns_key_when_set(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-key-for-test")
    from core.config import Settings
    s = Settings()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        key = s.jwt_secret_key
    assert key == "super-secret-key-for-test"
    assert len(w) == 0


def test_jwt_secret_warns_when_empty(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    from core.config import Settings
    s = Settings()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.jwt_secret_key
    assert len(w) > 0
    assert "RuntimeWarning" in str(w[0].category.__name__)


def test_jwt_algorithm_default(monkeypatch):
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.jwt_algorithm == "HS256"


def test_jwt_algorithm_custom(monkeypatch):
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    from core.config import Settings
    s = Settings()
    assert s.jwt_algorithm == "RS256"


# ---------------------------------------------------------------------------
# SMTP properties
# ---------------------------------------------------------------------------
def test_smtp_host_returns_none_when_not_set(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_host is None


def test_smtp_host_strips_whitespace(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "  smtp.gmail.com  ")
    from core.config import Settings
    s = Settings()
    assert s.smtp_host == "smtp.gmail.com"


def test_smtp_port_default(monkeypatch):
    monkeypatch.delenv("SMTP_PORT", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_port == 587


def test_smtp_port_custom(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")
    from core.config import Settings
    s = Settings()
    assert s.smtp_port == 465


def test_smtp_port_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "not-a-number")
    from core.config import Settings
    s = Settings()
    assert s.smtp_port == 587


def test_smtp_user_returns_none_when_not_set(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_user is None


def test_smtp_password_returns_none_when_not_set(monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_password is None


def test_smtp_sender_returns_none_when_not_set(monkeypatch):
    monkeypatch.delenv("SMTP_SENDER", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_sender is None


def test_smtp_sender_strips_whitespace(monkeypatch):
    monkeypatch.setenv("SMTP_SENDER", "  no-reply@example.com  ")
    from core.config import Settings
    s = Settings()
    assert s.smtp_sender == "no-reply@example.com"


def test_smtp_enabled_false_when_missing_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("SMTP_SENDER", "sender@example.com")
    from core.config import Settings
    s = Settings()
    assert s.smtp_enabled is False


def test_smtp_enabled_false_when_missing_sender(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_SENDER", raising=False)
    from core.config import Settings
    s = Settings()
    assert s.smtp_enabled is False


def test_smtp_enabled_true_when_both_set(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_SENDER", "no-reply@example.com")
    from core.config import Settings
    s = Settings()
    assert s.smtp_enabled is True


# ---------------------------------------------------------------------------
# get_settings lru_cache
# ---------------------------------------------------------------------------
def test_get_settings_returns_settings_instance():
    from core.config import get_settings, Settings
    s = get_settings()
    assert isinstance(s, Settings)


def test_get_settings_is_cached():
    from core.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
