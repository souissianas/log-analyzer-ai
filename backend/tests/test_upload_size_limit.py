import os
import tempfile
import unittest
from fastapi.testclient import TestClient

os.environ.pop("DATABASE_URL", None)

# SonarCloud: "'tempfile.mktemp' is insecure. Use 'tempfile.TemporaryFile' instead"
# mktemp() only returns a *name*, it never creates the file, leaving a race
# window (TOCTOU) before SQLite opens the path. mkstemp() creates the file
# atomically; we close the fd immediately since SQLite reopens by path.
_fd, _SQLITE_TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["SQLITE_DB_PATH"] = _SQLITE_TEST_DB_PATH
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-tests"

from core.config import get_settings  # noqa: E402
from core.jwt import create_access_token  # noqa: E402
from main import app  # noqa: E402
from services import storage  # noqa: E402

MAX_FILE_SIZE = get_settings().max_file_size


def _analyst_headers() -> dict:
    token = create_access_token(
        data={"sub": "analyst@test.com", "role": "analyst",
              "tenant_id": "t1", "user_id": "u1"}
    )
    return {"Authorization": f"Bearer {token}"}


class TestUploadSizeLimit(unittest.TestCase):
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

    def test_rejects_oversized_file_on_analyze_file(self):
        oversized = b"x" * (MAX_FILE_SIZE + 1)
        response = self.client.post(
            "/ollama/analyze-file",
            headers=_analyst_headers(),
            files={"file": ("big.log", oversized, "text/plain")},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10 MB", response.json()["detail"])

    def test_rejects_oversized_file_on_analyze(self):
        oversized = b"x" * (MAX_FILE_SIZE + 1)
        response = self.client.post(
            "/analyze",
            headers=_analyst_headers(),
            files={"file": ("big.log", oversized, "text/plain")},
        )
        self.assertEqual(response.status_code, 413)

    def test_accepts_file_at_limit(self):
        content = (
            b"2026-06-18 10:00:00 ERROR sample\n".ljust(MAX_FILE_SIZE, b" ")
        )
        response = self.client.post(
            "/ollama/analyze-file?max_errors=0",
            headers=_analyst_headers(),
            files={"file": ("limit.log", content, "text/plain")},
        )
        self.assertNotEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
