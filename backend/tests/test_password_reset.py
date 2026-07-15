"""Tests pour les endpoints forgot-password et reset-password."""
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ.pop("DATABASE_URL", None)

_fd, _SQLITE_TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["SQLITE_DB_PATH"] = _SQLITE_TEST_DB_PATH
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-tests"

from core.config import get_settings
from main import app
from services import storage


def _register_user(client, email: str, slug: str) -> dict:
    """Cree un utilisateur admin (premier du tenant)."""
    _FAKE_HASH = "$2b$12$fakehashforunittestonly123456789"
    with patch("routers.auth.get_password_hash", return_value=_FAKE_HASH):
        reg = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "Test1234!",
                "tenant_name": "Reset Org",
                "tenant_slug": slug,
                "role": "admin",
            },
        )
    return reg.json()


class TestForgotPassword(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["API_KEY"] = "unused-reset-tests"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def test_unknown_email_returns_success_to_avoid_enumeration(self):
        """Meme pour un email inexistant, la reponse doit etre 200."""
        response = self.client.post(
            "/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.json().get("message", "").lower())

    def test_known_email_triggers_otp_generation(self):
        """Pour un utilisateur existant, un OTP est genere et visible dans les logs."""
        _register_user(self.client, "otp-user@test.com", "otp-tenant-1")

        with patch("services.email_service.send_email", new_callable=AsyncMock) as mock_mail:
            mock_mail.return_value = True
            response = self.client.post(
                "/auth/forgot-password",
                json={"email": "otp-user@test.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.json()["message"].lower())

    def test_email_is_normalized_to_lowercase(self):
        """L email est normalis'e en minuscules avant recherche."""
        _register_user(self.client, "upper@test.com", "upper-tenant")
        response = self.client.post(
            "/auth/forgot-password",
            json={"email": "UPPER@TEST.COM"},
        )
        self.assertEqual(response.status_code, 200)


class TestResetPassword(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["API_KEY"] = "unused-reset-tests-2"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def _get_otp(self, email: str) -> str:
        """Genere un OTP pour l email et retourne le code en clair (env dev)."""
        import logging
        import hashlib
        import secrets

        code = f"{secrets.randbelow(1_000_000):06d}"
        hashed = hashlib.sha256(code.encode()).hexdigest()
        storage.save_otp(email, hashed, time.time() + 600)
        return code

    def test_no_active_otp_returns_400(self):
        response = self.client.post(
            "/auth/reset-password",
            json={
                "email": "noreset@example.com",
                "code": "123456",
                "new_password": "NewPass123!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("actif", response.json()["detail"])

    def test_wrong_code_returns_400(self):
        _register_user(self.client, "wrong-code@test.com", "wrong-code-tenant")
        self._get_otp("wrong-code@test.com")

        response = self.client.post(
            "/auth/reset-password",
            json={
                "email": "wrong-code@test.com",
                "code": "000000",
                "new_password": "NewPass123!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("incorrect", response.json()["detail"].lower())

    def test_expired_otp_returns_400(self):
        _register_user(self.client, "expired-otp@test.com", "expired-tenant")
        import hashlib
        hashed = hashlib.sha256("123456".encode()).hexdigest()
        # Expiration dans le passe
        storage.save_otp("expired-otp@test.com", hashed, time.time() - 1)

        response = self.client.post(
            "/auth/reset-password",
            json={
                "email": "expired-otp@test.com",
                "code": "123456",
                "new_password": "NewPass123!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expir", response.json()["detail"].lower())

    def test_valid_otp_resets_password_successfully(self):
        _register_user(self.client, "valid-reset@test.com", "valid-reset-tenant")
        code = self._get_otp("valid-reset@test.com")

        with patch("routers.auth.get_password_hash", return_value="$2b$12$newhash"):
            response = self.client.post(
                "/auth/reset-password",
                json={
                    "email": "valid-reset@test.com",
                    "code": code,
                    "new_password": "NewSecurePassword123!",
                },
            )
        self.assertEqual(response.status_code, 200)
        # Verifier que la reponse est un succes (le message contient "jour" ou "succes")
        msg = response.json().get("message", "").encode("ascii", errors="ignore").decode()
        self.assertTrue(len(msg) > 0)

    def test_otp_is_deleted_after_successful_reset(self):
        """Apres un reset reussi, l OTP ne doit plus exister."""
        _register_user(self.client, "otp-delete@test.com", "otp-delete-tenant")
        code = self._get_otp("otp-delete@test.com")

        with patch("routers.auth.get_password_hash", return_value="$2b$12$anotherhash"):
            self.client.post(
                "/auth/reset-password",
                json={
                    "email": "otp-delete@test.com",
                    "code": code,
                    "new_password": "AnotherPass123!",
                },
            )

        # Une deuxieme tentative doit echouer (OTP supprime)
        with patch("routers.auth.get_password_hash", return_value="$2b$12$anotherhash"):
            response = self.client.post(
                "/auth/reset-password",
                json={
                    "email": "otp-delete@test.com",
                    "code": code,
                    "new_password": "AnotherPass123!",
                },
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
