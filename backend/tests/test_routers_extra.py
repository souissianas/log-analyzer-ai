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
import unittest
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

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _token(role="analyst", email="u@test.com", tenant_id="t1", user_id="u1"):
    return create_access_token(
        data={"sub": email, "role": role, "tenant_id": tenant_id, "user_id": user_id}
    )

def _headers(role="analyst"):
    return {"Authorization": f"Bearer {_token(role)}"}


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoints
# ─────────────────────────────────────────────────────────────────────────────
class TestHealthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        storage.init_db()
        cls.client = TestClient(app)

    # GET /
    def test_root_returns_200(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("message", r.json())

    # GET /health
    def test_health_check_returns_ok(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    # GET /health/ready — DB ok, Ollama ok
    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    @patch("routers.health.storage.check_db_health")
    def test_readiness_check_returns_200_when_ready(self, mock_db, mock_ollama):
        mock_db.return_value = {"ok": True}
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": True,
            "required_model": "llama3.2",
        }
        r = self.client.get("/health/ready")
        self.assertEqual(r.status_code, 200)

    # GET /health/ready — DB ok, Ollama down → 503
    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    @patch("routers.health.storage.check_db_health")
    def test_readiness_check_returns_503_when_degraded(self, mock_db, mock_ollama):
        mock_db.return_value = {"ok": True}
        mock_ollama.return_value = {
            "ollama_running": False,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = self.client.get("/health/ready")
        self.assertEqual(r.status_code, 503)

    # GET /ollama/health — Ollama running, model ok
    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    def test_ollama_health_returns_200_when_ok(self, mock_ollama):
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": True,
            "required_model": "llama3.2",
        }
        r = self.client.get("/ollama/health")
        self.assertEqual(r.status_code, 200)

    # GET /ollama/health — Ollama not running → 503
    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    def test_ollama_health_returns_503_when_not_running(self, mock_ollama):
        mock_ollama.return_value = {
            "ollama_running": False,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = self.client.get("/ollama/health")
        self.assertEqual(r.status_code, 503)

    # GET /ollama/health — running but no model → 503
    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    def test_ollama_health_returns_503_when_model_missing(self, mock_ollama):
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": False,
            "required_model": "llama3.2",
        }
        r = self.client.get("/ollama/health")
        self.assertEqual(r.status_code, 503)


# ─────────────────────────────────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────────────────────────────────
class TestAdminEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Disable API key auth for these tests
        cls._prev_key = os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_key:
            os.environ["API_KEY"] = cls._prev_key
        get_settings.cache_clear()

    # POST /db/migrate — no DATABASE_URL → 400
    def test_migrate_returns_400_when_no_database_url(self):
        with patch("routers.admin.storage.DATABASE_URL", None):
            r = self.client.post("/db/migrate")
        self.assertEqual(r.status_code, 400)

    # POST /db/migrate — DATABASE_URL set but psycopg2 not installed → 500
    def test_migrate_returns_500_when_no_psycopg2(self):
        # patch only DATABASE_URL; psycopg2 is not installed in CI so getattr returns None → 500
        with patch("routers.admin.storage.DATABASE_URL", "postgresql://host/db"):
            r = self.client.post("/db/migrate")
        self.assertEqual(r.status_code, 500)

    # POST /db/migrate — success
    def test_migrate_returns_200_on_success(self):
        with patch("routers.admin.storage.DATABASE_URL", "postgres://x"), \
             patch.object(storage, "psycopg2", MagicMock()), \
             patch("routers.admin.storage.migrate_sqlite_to_postgres", return_value={"rows": 5}):
            r = self.client.post("/db/migrate")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])


# ─────────────────────────────────────────────────────────────────────────────
# Logs endpoints
# ─────────────────────────────────────────────────────────────────────────────
class TestLogsEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep auth disabled (no API_KEY) so JWT Bearer tokens are validated
        # Note: when auth_enabled=False, all users pass as admin.
        # For 403 role checks we need auth enabled — handled per-test.
        cls._prev_key = os.environ.pop("API_KEY", None)
        get_settings.cache_clear()
        storage.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_key:
            os.environ["API_KEY"] = cls._prev_key
        get_settings.cache_clear()

    # GET /stats/dashboard
    @patch("routers.logs.storage.get_dashboard_stats")
    def test_dashboard_stats_returns_200(self, mock_stats):
        mock_stats.return_value = {"total_analyses": 5, "total_errors": 10}
        r = self.client.get("/stats/dashboard", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)

    # GET /logs — empty list
    def test_list_analyses_returns_200(self):
        r = self.client.get("/logs", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("items", r.json())

    # GET /logs/{id} — not found → 404
    def test_get_analysis_not_found_returns_404(self):
        r = self.client.get("/logs/99999", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 404)

    # GET /logs/{id} — found
    @patch("routers.logs.storage.get_analysis")
    def test_get_analysis_found_returns_200(self, mock_get):
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18T10:00:00",
            "total_errors_found": 2, "total_analyzed": 2, "data": {}
        }
        r = self.client.get("/logs/1", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)

    # POST /logs/{id}/export — viewer → 403 (needs auth enabled to check role)
    def test_export_pdf_viewer_returns_403(self):
        os.environ["API_KEY"] = "test-key"
        get_settings.cache_clear()
        try:
            r = self.client.post("/logs/1/export", headers=_headers("viewer"))
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    # POST /logs/{id}/export — analyst + not found → 404
    def test_export_pdf_analyst_not_found_returns_404(self):
        with patch("routers.logs.storage.get_analysis", return_value=None):
            r = self.client.post("/logs/1/export", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 404)

    # POST /logs/{id}/export — analyst + found → 200 PDF
    @patch("routers.logs.build_analysis_pdf")
    @patch("routers.logs.storage.get_analysis")
    def test_export_pdf_analyst_found_returns_pdf(self, mock_get, mock_pdf):
        import io
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18",
            "total_errors_found": 1, "total_analyzed": 1, "data": {}
        }
        mock_pdf.return_value = io.BytesIO(b"%PDF-1.4")
        r = self.client.post("/logs/1/export", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("pdf", r.headers.get("content-type", ""))

    # POST /logs/{id}/reanalyze — viewer → 403 (needs auth enabled to check role)
    def test_reanalyze_viewer_returns_403(self):
        os.environ["API_KEY"] = "test-key"
        get_settings.cache_clear()
        try:
            r = self.client.post("/logs/1/reanalyze", headers=_headers("viewer"))
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    # POST /logs/{id}/reanalyze — analyst + not found → 404
    def test_reanalyze_analyst_not_found_returns_404(self):
        with patch("routers.logs.storage.get_analysis", return_value=None):
            r = self.client.post("/logs/1/reanalyze", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 404)

    # POST /logs/{id}/reanalyze — found + empty analyzed list
    @patch("routers.logs.storage.save_analysis", return_value=42)
    @patch("routers.logs.storage.get_analysis")
    def test_reanalyze_analyst_found_empty_analyzed(self, mock_get, mock_save):
        mock_get.return_value = {
            "id": 1, "filename": "app.log", "created_at": "2026-06-18",
            "total_errors_found": 0, "total_analyzed": 0,
            "data": {"filename": "app.log", "analyzed": []},
        }
        r = self.client.post("/logs/1/reanalyze", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("new_log_id", r.json())

    # POST /logs/{id}/reanalyze — found + with errors (mocks Ollama)
    @patch("routers.logs.analyze_with_ollama", new_callable=AsyncMock)
    @patch("routers.logs.storage.save_analysis", return_value=43)
    @patch("routers.logs.storage.get_analysis")
    def test_reanalyze_analyst_found_with_errors(self, mock_get, mock_save, mock_ollama):
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
        r = self.client.post("/logs/1/reanalyze", headers=_headers("analyst"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["new_log_id"], 43)
        self.assertEqual(len(data["result"]["analyzed"]), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Security — require_api_key
# ─────────────────────────────────────────────────────────────────────────────
class TestRequireApiKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        storage.init_db()
        cls.client = TestClient(app)

    def test_migrate_rejected_when_wrong_api_key(self):
        os.environ["API_KEY"] = "correct-key"
        get_settings.cache_clear()
        try:
            r = self.client.post("/db/migrate", headers={"x-api-key": "wrong-key"})
            self.assertEqual(r.status_code, 401)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_migrate_rejected_when_no_api_key_provided(self):
        os.environ["API_KEY"] = "my-key"
        get_settings.cache_clear()
        try:
            r = self.client.post("/db/migrate")
            self.assertEqual(r.status_code, 401)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_migrate_accepted_with_correct_api_key(self):
        os.environ["API_KEY"] = "valid-key"
        get_settings.cache_clear()
        try:
            with patch("routers.admin.storage.DATABASE_URL", None):
                r = self.client.post("/db/migrate", headers={"x-api-key": "valid-key"})
            # 400 = auth ok, fails due to no DATABASE_URL (correct behaviour)
            self.assertEqual(r.status_code, 400)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_get_current_user_returns_401_without_auth(self):
        # Auth only enforced when API_KEY is set
        os.environ["API_KEY"] = "test-key"
        get_settings.cache_clear()
        try:
            r = self.client.get("/logs")
            self.assertEqual(r.status_code, 401)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_get_current_user_returns_401_with_bad_token(self):
        os.environ["API_KEY"] = "test-key"
        get_settings.cache_clear()
        try:
            r = self.client.get("/logs", headers={"Authorization": "Bearer bad.token.here"})
            self.assertEqual(r.status_code, 401)
        finally:
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()
