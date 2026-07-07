import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ.pop("DATABASE_URL", None)
os.environ["SQLITE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-tests"

from core.config import get_settings  # noqa: E402
from core.jwt import create_access_token  # noqa: E402
from main import app  # noqa: E402
from services import storage  # noqa: E402


def _analyst_headers() -> dict:
    """Génère les headers Authorization avec un token JWT analyst."""
    token = create_access_token(
        data={"sub": "analyst@test.com", "role": "analyst",
              "tenant_id": "t1", "user_id": "u1"}
    )
    return {"Authorization": f"Bearer {token}"}


class TestAnalyzeFileAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_api_key = os.environ.pop("API_KEY", None)
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_api_key:
            os.environ["API_KEY"] = cls._previous_api_key
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)
        self.sample_log = (
            b"2026-06-18 10:00:00 INFO Starting app\n"
            b"2026-06-18 10:00:01 ERROR Connection timeout to database\n"
            b"2026-06-18 10:00:02 CRITICAL Memory usage exceeded threshold\n"
        )

    @patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock)
    def test_analyze_file_returns_contract(self, mock_ollama):
        mock_ollama.return_value = {
            "success": True,
            "analysis": {
                "explanation": "Timeout de connexion.",
                "causes": ["Service indisponible"],
                "solutions": ["Verifier le reseau"],
            },
            "raw_response": "{}",
            "error": None,
        }

        response = self.client.post(
            "/ollama/analyze-file?output_format=json&max_errors=5",
            headers=_analyst_headers(),
            files={"file": ("test.log", self.sample_log, "text/plain")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["filename"], "test.log")
        self.assertEqual(data["total_errors_found"], 2)
        self.assertIn("log_id", data)
        self.assertEqual(len(data["analyzed"]), 2)
        self.assertEqual(data["analyzed"][0]["category"], "connection")
        self.assertTrue(mock_ollama.called)

    def test_analyze_rejects_unsupported_extension(self):
        response = self.client.post(
            "/ollama/analyze-file",
            headers=_analyst_headers(),
            files={"file": ("report.csv", b"2026-06-18 10:00:00 ERROR fail", "text/csv")},
        )

        self.assertEqual(response.status_code, 400)

    @patch("routers.analyze.explain_logs", new_callable=AsyncMock)
    def test_analyze_endpoint_accepts_txt(self, mock_explain):
        mock_explain.return_value = "Analyse globale simulee."

        response = self.client.post(
            "/analyze",
            headers=_analyst_headers(),
            files={"file": ("events.txt", self.sample_log, "text/plain")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["filename"], "events.txt")
        self.assertGreaterEqual(data["summary"]["total_critical"], 1)


class TestHealthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_api_key = os.environ.pop("API_KEY", None)
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_api_key:
            os.environ["API_KEY"] = cls._previous_api_key
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def test_health_liveness(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_metrics_endpoint(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("http_requests_total", response.text)

    @patch("routers.health.check_ollama_health", new_callable=AsyncMock)
    def test_health_ready_reports_database(self, mock_ollama):
        mock_ollama.return_value = {
            "ollama_running": True,
            "model_available": True,
            "available_models": ["llama3.2"],
            "required_model": "llama3.2",
        }

        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["database"]["ok"])


if __name__ == "__main__":
    unittest.main()
