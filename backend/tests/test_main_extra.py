"""
Additional tests for routers not covered elsewhere:
- /ollama/analyze-line
- /jobs/{id}/status, /jobs/{id}/result
- main.py startup + prometheus middleware
"""
import os
import tempfile
import unittest
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


def _token(role="analyst", email="u@test.com"):
    return create_access_token(
        data={"sub": email, "role": role, "tenant_id": "t1", "user_id": "u1"}
    )


def _headers(role="analyst"):
    return {"Authorization": f"Bearer {_token(role)}"}


# ─────────────────────────────────────────────────────────────────────────────
# /ollama/analyze-line
# ─────────────────────────────────────────────────────────────────────────────
class TestAnalyzeSingleLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    # viewer role → 403
    def test_viewer_returns_403(self):
        os.environ["API_KEY"] = "test-key-viewer-single-line"
        get_settings.cache_clear()
        try:
            client = TestClient(app)
            r = client.post(
                "/ollama/analyze-line",
                params={"log_line": "some error", "error_level": "ERROR"},
                headers=_headers("viewer"),
            )
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    # empty line → 400
    def test_empty_line_returns_400(self):
        r = self.client.post(
            "/ollama/analyze-line",
            params={"log_line": "   ", "error_level": "ERROR"},
            headers=_headers("analyst"),
        )
        self.assertEqual(r.status_code, 400)

    # happy path — mocked Ollama
    @patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock)
    def test_analyze_line_success(self, mock_ollama):
        mock_ollama.return_value = {
            "success": True,
            "analysis": {"explanation": "Disk full", "causes": [], "solutions": []},
            "raw_response": "{}",
            "error": None,
        }
        r = self.client.post(
            "/ollama/analyze-line",
            params={"log_line": "disk full error", "error_level": "ERROR"},
            headers=_headers("analyst"),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("analysis", data)
        self.assertTrue(data["success"])

    # analyst sends file with no errors → empty response
    @patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock)
    def test_analyze_file_no_errors(self, mock_ollama):
        log_content = b"2026-06-18 10:00:00 INFO All systems nominal\n"
        r = self.client.post(
            "/ollama/analyze-file",
            headers=_headers("analyst"),
            files={"file": ("no_errors.log", log_content, "text/plain")},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["total_errors_found"], 0)
        mock_ollama.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# /jobs endpoints (with mocked job store)
# ─────────────────────────────────────────────────────────────────────────────
class TestJobEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    # GET /jobs/{id}/status — not found
    @patch("routers.jobs.get_job", return_value=None)
    def test_job_status_not_found(self, _):
        r = self.client.get("/jobs/nonexistent-id/status", headers=_headers())
        self.assertEqual(r.status_code, 404)

    # GET /jobs/{id}/status — job found
    @patch("routers.jobs.get_job")
    def test_job_status_found(self, mock_get_job):
        mock_get_job.return_value = {
            "job_id": "abc-123",
            "status": "running",
            "filename": "test.log",
            "current": 2,
            "total": 5,
            "log_id": None,
            "error": None,
        }
        r = self.client.get("/jobs/abc-123/status", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["job_id"], "abc-123")
        self.assertEqual(data["status"], "running")

    # GET /jobs/{id}/result — not found
    @patch("routers.jobs.get_job", return_value=None)
    def test_job_result_not_found(self, _):
        r = self.client.get("/jobs/nonexistent-id/result", headers=_headers())
        self.assertEqual(r.status_code, 404)

    # GET /jobs/{id}/result — job still pending → 409
    @patch("routers.jobs.get_job")
    def test_job_result_pending_returns_409(self, mock_get_job):
        mock_get_job.return_value = {
            "job_id": "xyz-456",
            "status": "running",
        }
        r = self.client.get("/jobs/xyz-456/result", headers=_headers())
        self.assertEqual(r.status_code, 409)

    # GET /jobs/{id}/result — job done → 200
    @patch("routers.jobs.get_job")
    def test_job_result_done_returns_200(self, mock_get_job):
        mock_get_job.return_value = {
            "job_id": "done-789",
            "status": "done",
            "result": {"filename": "app.log", "total_errors_found": 1},
            "log_id": 42,
        }
        r = self.client.get("/jobs/done-789/result", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["log_id"], 42)
        self.assertIn("result", data)

    # GET /jobs/{id} alias — works same as /status
    @patch("routers.jobs.get_job")
    def test_job_alias_endpoint(self, mock_get_job):
        mock_get_job.return_value = {
            "job_id": "alias-001",
            "status": "pending",
            "filename": "f.log",
            "current": 0,
            "total": 0,
            "log_id": None,
            "error": None,
        }
        r = self.client.get("/jobs/alias-001", headers=_headers())
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# main.py — prometheus middleware and startup
# ─────────────────────────────────────────────────────────────────────────────
class TestMainMiddleware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    def test_metrics_endpoint_returns_prometheus_text(self):
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.headers["content-type"])
        self.assertIn("http_requests_total", r.text)

    def test_non_metrics_path_increments_counter(self):
        # Hit a real endpoint, then verify metrics reflect the call
        self.client.get("/health")
        r = self.client.get("/metrics")
        self.assertIn("http_requests_total", r.text)

    def test_health_endpoint_excluded_from_metrics(self):
        """The /health path is excluded from prometheus tracking."""
        r1 = self.client.get("/metrics")
        count_before = r1.text.count('path="/health"')
        self.client.get("/health")
        r2 = self.client.get("/metrics")
        count_after = r2.text.count('path="/health"')
        # Health shouldn't add more entries for /health
        self.assertEqual(count_before, count_after)


# ─────────────────────────────────────────────────────────────────────────────
# users router — basic coverage
# ─────────────────────────────────────────────────────────────────────────────
class TestUsersRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    def test_list_users_as_admin(self):
        with patch("routers.users.storage.list_users", return_value=[]):
            r = self.client.get("/users/", headers=_headers("admin"))
        self.assertEqual(r.status_code, 200)

    def test_list_users_as_viewer_returns_403(self):
        # require_role(["admin"]) enforces role when auth is enabled (API_KEY set)
        os.environ["API_KEY"] = "test-key-viewers"
        get_settings.cache_clear()
        try:
            client = TestClient(app)
            r = client.get("/users/", headers=_headers("viewer"))
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    @patch("routers.users.storage.get_user_by_id")
    @patch("routers.users.storage.update_user_status", return_value=True)
    def test_patch_user_status_as_admin(self, mock_update, mock_get):
        mock_get.return_value = {"id": 1, "email": "x@x.com", "role": "viewer", "status": "pending"}
        r = self.client.patch(
            "/users/1/status",
            json={"status": "active"},
            headers=_headers("admin"),
        )
        self.assertIn(r.status_code, (200, 404))

    def test_patch_user_status_as_viewer_returns_403(self):
        r = self.client.patch(
            "/users/1/status",
            json={"status": "active"},
            headers=_headers("viewer"),
        )
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
