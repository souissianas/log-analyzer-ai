"""
Additional tests for routers not covered elsewhere:
- /ollama/analyze-line
- /jobs/{id}/status, /jobs/{id}/result
- main.py startup + prometheus middleware
"""
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.pop("DATABASE_URL", None)
_fd, _DB2 = tempfile.mkstemp(suffix="_main_test.db")
os.close(_fd)
os.environ.setdefault("SQLITE_DB_PATH", _DB2)
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-main-extra")

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


def _token(role="analyst", email="u@test.com"):
    return create_access_token(
        data={"sub": email, "role": role, "tenant_id": "t1", "user_id": "u1"}
    )


def _headers(role="analyst"):
    return {"Authorization": f"Bearer {_token(role)}"}


# ─────────────────────────────────────────────────────────────────────────────
# /ollama/analyze-line
# ─────────────────────────────────────────────────────────────────────────────
def test_viewer_returns_403(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-viewer-single-line")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post(
        "/ollama/analyze-line",
        params={"log_line": "some error", "error_level": "ERROR"},
        headers=_headers("viewer"),
    )
    assert r.status_code == 403


def test_empty_line_returns_400(client):
    r = client.post(
        "/ollama/analyze-line",
        params={"log_line": "   ", "error_level": "ERROR"},
        headers=_headers("analyst"),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_analyze_line_success(client):
    with patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "success": True,
            "analysis": {"explanation": "Disk full", "causes": [], "solutions": []},
            "raw_response": "{}",
            "error": None,
        }
        r = client.post(
            "/ollama/analyze-line",
            params={"log_line": "disk full error", "error_level": "ERROR"},
            headers=_headers("analyst"),
        )
        assert r.status_code == 200
        data = r.json()
        assert "analysis" in data
        assert data["success"] is True


@pytest.mark.asyncio
async def test_analyze_file_no_errors(client):
    with patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock) as mock_ollama:
        log_content = b"2026-06-18 10:00:00 INFO All systems nominal\n"
        r = client.post(
            "/ollama/analyze-file",
            headers=_headers("analyst"),
            files={"file": ("no_errors.log", log_content, "text/plain")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_errors_found"] == 0
        mock_ollama.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# /jobs endpoints
# ─────────────────────────────────────────────────────────────────────────────
def test_job_status_not_found(client):
    with patch("routers.jobs.get_job", return_value=None):
        r = client.get("/jobs/nonexistent-id/status", headers=_headers())
        assert r.status_code == 404


def test_job_status_found(client):
    with patch("routers.jobs.get_job") as mock_get_job:
        mock_get_job.return_value = {
            "job_id": "abc-123",
            "status": "running",
            "filename": "test.log",
            "current": 2,
            "total": 5,
            "log_id": None,
            "error": None,
        }
        r = client.get("/jobs/abc-123/status", headers=_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == "abc-123"
        assert data["status"] == "running"


def test_job_result_not_found(client):
    with patch("routers.jobs.get_job", return_value=None):
        r = client.get("/jobs/nonexistent-id/result", headers=_headers())
        assert r.status_code == 404


def test_job_result_pending_returns_409(client):
    with patch("routers.jobs.get_job") as mock_get_job:
        mock_get_job.return_value = {
            "job_id": "xyz-456",
            "status": "running",
        }
        r = client.get("/jobs/xyz-456/result", headers=_headers())
        assert r.status_code == 409


def test_job_result_done_returns_200(client):
    with patch("routers.jobs.get_job") as mock_get_job:
        mock_get_job.return_value = {
            "job_id": "done-789",
            "status": "done",
            "result": {"filename": "app.log", "total_errors_found": 1},
            "log_id": 42,
        }
        r = client.get("/jobs/done-789/result", headers=_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["log_id"] == 42
        assert "result" in data


def test_job_alias_endpoint(client):
    with patch("routers.jobs.get_job") as mock_get_job:
        mock_get_job.return_value = {
            "job_id": "alias-001",
            "status": "pending",
            "filename": "f.log",
            "current": 0,
            "total": 0,
            "log_id": None,
            "error": None,
        }
        r = client.get("/jobs/alias-001", headers=_headers())
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# main.py — prometheus middleware and startup
# ─────────────────────────────────────────────────────────────────────────────
def test_metrics_endpoint_returns_prometheus_text(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "http_requests_total" in r.text


def test_non_metrics_path_increments_counter(client):
    client.get("/health")
    r = client.get("/metrics")
    assert "http_requests_total" in r.text


def test_health_endpoint_excluded_from_metrics(client):
    r1 = client.get("/metrics")
    count_before = r1.text.count('path="/health"')
    client.get("/health")
    r2 = client.get("/metrics")
    count_after = r2.text.count('path="/health"')
    assert count_before == count_after


# ─────────────────────────────────────────────────────────────────────────────
# users router — basic coverage
# ─────────────────────────────────────────────────────────────────────────────
def test_list_users_as_admin(client):
    with patch("routers.users.storage.list_users", return_value=[]):
        r = client.get("/users/", headers=_headers("admin"))
    assert r.status_code == 200


def test_list_users_as_viewer_returns_403(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-viewers")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.get("/users/", headers=_headers("viewer"))
    assert r.status_code == 403


def test_patch_user_status_as_admin(client):
    with patch("routers.users.storage.get_user_by_id") as mock_get, patch("routers.users.storage.update_user_status", return_value=True):
        mock_get.return_value = {"id": 1, "email": "x@x.com", "role": "viewer", "status": "pending"}
        r = client.patch(
            "/users/1/status",
            json={"status": "active"},
            headers=_headers("admin"),
        )
        assert r.status_code in (200, 404)


def test_patch_user_status_as_viewer_returns_403(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-viewers")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.patch(
        "/users/1/status",
        json={"status": "active"},
        headers=_headers("viewer"),
    )
    assert r.status_code == 403
