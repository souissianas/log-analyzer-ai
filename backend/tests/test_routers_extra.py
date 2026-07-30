"""
Tests supplementaires pour les routes peu couvertes :
  - GET /health, /health/ready, /ollama/health
  - POST /db/migrate
  - GET /logs, GET /logs/{id}, POST /logs/{id}/export, POST /logs/{id}/reanalyze
  - GET /stats/dashboard
  - core/security : require_api_key, require_role
"""
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.pop("DATABASE_URL", None)
_fd, _SQLITE_TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.setdefault("SQLITE_DB_PATH", _SQLITE_TEST_DB_PATH)
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-extra-tests")

from fastapi.testclient import TestClient
from core.config import get_settings
from core.jwt import create_access_token
from main import app
from services import storage


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    get_settings.cache_clear()
    storage.init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _token(role="analyst", email="u@test.com", tenant_id="t1", user_id="u1"):
    return create_access_token(
        data={"sub": email, "role": role, "tenant_id": tenant_id, "user_id": user_id}
    )


def _headers(role="analyst"):
    return {"Authorization": f"Bearer {_token(role)}"}


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoints
# ─────────────────────────────────────────────────────────────────────────────
def test_root_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()


def test_health_check_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_check_returns_200_when_ready(client):
    with patch("routers.health.storage.check_db_health", return_value={"ok": True}), \
         patch("routers.health.check_ollama_health", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": True,
            "required_model": "llama3.2",
        }
        r = client.get("/health/ready")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_readiness_check_returns_503_when_degraded(client):
    with patch("routers.health.storage.check_db_health", return_value={"ok": True}), \
         patch("routers.health.check_ollama_health", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "ollama_running": False,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = client.get("/health/ready")
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_ollama_health_returns_200_when_ok(client):
    with patch("routers.health.check_ollama_health", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": True,
            "required_model": "llama3.2",
        }
        r = client.get("/ollama/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_ollama_health_returns_503_when_not_running(client):
    with patch("routers.health.check_ollama_health", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "ollama_running": False,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = client.get("/ollama/health")
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_ollama_health_returns_503_when_model_missing(client):
    with patch("routers.health.check_ollama_health", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = client.get("/ollama/health")
        assert r.status_code == 503


# ─────────────────────────────────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────────────────────────────────
def test_migrate_returns_400_when_no_database_url(client):
    with patch("routers.admin.storage.DATABASE_URL", None):
        r = client.post("/db/migrate")
    assert r.status_code == 400


def test_migrate_returns_500_when_no_psycopg2(client):
    with patch("routers.admin.storage.DATABASE_URL", "postgresql://host/db"):
        r = client.post("/db/migrate")
    assert r.status_code == 500


def test_migrate_returns_200_on_success(client):
    with patch("routers.admin.storage.DATABASE_URL", "postgres://x"), \
         patch.object(storage, "psycopg2", MagicMock()), \
         patch("routers.admin.storage.migrate_sqlite_to_postgres", return_value={"rows": 5}):
        r = client.post("/db/migrate")
    assert r.status_code == 200
    assert r.json()["success"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Logs endpoints
# ─────────────────────────────────────────────────────────────────────────────
def test_dashboard_stats_returns_200(client):
    with patch("routers.logs.storage.get_dashboard_stats") as mock_stats:
        mock_stats.return_value = {"total_analyses": 5, "total_errors": 10}
        r = client.get("/stats/dashboard", headers=_headers("analyst"))
        assert r.status_code == 200


def test_list_analyses_returns_200(client):
    r = client.get("/logs", headers=_headers("analyst"))
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_analysis_not_found_returns_404(client):
    r = client.get("/logs/99999", headers=_headers("analyst"))
    assert r.status_code == 404


def test_get_analysis_found_returns_200(client):
    with patch("routers.logs.storage.get_analysis") as mock_get:
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18T10:00:00",
            "total_errors_found": 2, "total_analyzed": 2, "data": {}
        }
        r = client.get("/logs/1", headers=_headers("analyst"))
        assert r.status_code == 200


def test_export_pdf_viewer_allowed(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post("/logs/1/export", headers=_headers("viewer"))
    assert r.status_code == 404


def test_export_pdf_analyst_not_found_returns_404(client):
    with patch("routers.logs.storage.get_analysis", return_value=None):
        r = client.post("/logs/1/export", headers=_headers("analyst"))
    assert r.status_code == 404


def test_export_pdf_analyst_found_returns_pdf(client):
    import io
    with patch("routers.logs.storage.get_analysis") as mock_get, patch("routers.logs.build_analysis_pdf") as mock_pdf:
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18",
            "total_errors_found": 1, "total_analyzed": 1, "data": {}
        }
        mock_pdf.return_value = io.BytesIO(b"%PDF-1.4")
        r = client.post("/logs/1/export", headers=_headers("analyst"))
        assert r.status_code == 200
        assert "pdf" in r.headers.get("content-type", "")


def test_reanalyze_viewer_returns_403(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post("/logs/1/reanalyze", headers=_headers("viewer"))
    assert r.status_code == 403


def test_reanalyze_analyst_not_found_returns_404(client):
    with patch("routers.logs.storage.get_analysis", return_value=None):
        r = client.post("/logs/1/reanalyze", headers=_headers("analyst"))
    assert r.status_code == 404


def test_reanalyze_analyst_found_empty_analyzed(client):
    with patch("routers.logs.storage.get_analysis") as mock_get, patch("routers.logs.storage.save_analysis", return_value=42):
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18",
            "total_errors_found": 0, "total_analyzed": 0,
            "data": {"filename": "app.log", "analyzed": []},
        }
        r = client.post("/logs/1/reanalyze", headers=_headers("analyst"))
        assert r.status_code == 200
        assert "new_log_id" in r.json()


@pytest.mark.asyncio
async def test_reanalyze_analyst_found_with_errors(client):
    with patch("routers.logs.storage.get_analysis") as mock_get, \
         patch("routers.logs.storage.save_analysis", return_value=43), \
         patch("routers.logs.analyze_with_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18",
            "total_errors_found": 1, "total_analyzed": 1,
            "data": {
                "filename": "app.log",
                "analyzed": [
                    {"timestamp": "2026-06-18", "level": "ERROR",
                     "message": "timeout", "line_number": 5}
                ],
            },
        }
        mock_ollama.return_value = {
            "success": True,
            "analysis": {"explanation": "Timeout.", "causes": [], "solutions": []},
            "error": None,
            "rag_used": False,
        }
        r = client.post("/logs/1/reanalyze", headers=_headers("analyst"))
        assert r.status_code == 200
        data = r.json()
        assert data["new_log_id"] == 43
        assert len(data["result"]["analyzed"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Security — require_api_key
# ─────────────────────────────────────────────────────────────────────────────
def test_migrate_rejected_when_wrong_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "correct-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post("/db/migrate", headers={"x-api-key": "wrong-key"})
    assert r.status_code == 401


def test_migrate_rejected_when_no_api_key_provided(monkeypatch):
    monkeypatch.setenv("API_KEY", "my-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post("/db/migrate")
    assert r.status_code == 401


def test_migrate_accepted_with_correct_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "valid-key")
    get_settings.cache_clear()
    c = TestClient(app)
    with patch("routers.admin.storage.DATABASE_URL", None):
        r = c.post("/db/migrate", headers={"x-api-key": "valid-key"})
    assert r.status_code == 400


def test_get_current_user_returns_401_without_auth(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.get("/logs")
    assert r.status_code == 401


def test_get_current_user_returns_401_with_bad_token(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.get("/logs", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401
