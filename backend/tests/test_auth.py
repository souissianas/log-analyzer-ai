"""Tests pour le système d'authentification JWT + API Key."""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

# SQLite en mémoire — pas besoin de PostgreSQL
os.environ.pop("DATABASE_URL", None)
os.environ["SQLITE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-tests"

from core.config import get_settings  # noqa: E402
from core.jwt import create_access_token  # noqa: E402
from main import app  # noqa: E402
from services import storage  # noqa: E402


def _make_jwt(role: str = "analyst", tenant_id: str = "t1", user_id: str = "u1") -> str:
    """Génère un token JWT de test."""
    return create_access_token(
        data={"sub": f"test-{role}@example.com", "role": role,
              "tenant_id": tenant_id, "user_id": user_id}
    )


class TestApiKeyAuth(unittest.TestCase):
    """Compatibilité API Key legacy (header X-API-Key)."""

    @classmethod
    def setUpClass(cls):
        cls._previous_api_key = os.environ.get("API_KEY")
        os.environ["API_KEY"] = "test-secret-key"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_api_key:
            os.environ["API_KEY"] = cls._previous_api_key
        else:
            os.environ.pop("API_KEY", None)
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def test_protected_route_rejects_no_credentials(self):
        """Sans credentials → 401."""
        response = self.client.get("/logs")
        self.assertEqual(response.status_code, 401)

    def test_protected_route_accepts_valid_api_key(self):
        """X-API-Key valide → 200."""
        response = self.client.get(
            "/logs",
            headers={"X-API-Key": "test-secret-key"},
        )
        self.assertEqual(response.status_code, 200)

    def test_health_routes_remain_public(self):
        """/health est toujours public."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)


class TestJwtAuth(unittest.TestCase):
    """Authentification JWT Bearer."""

    @classmethod
    def setUpClass(cls):
        # NOTE : settings.auth_enabled n'est vrai que si API_KEY est défini
        # (voir core/config.py). Le POPER complètement désactiverait TOUT
        # le système d'auth (voir core/security.py: `if not auth_enabled:
        # return anonymous admin`), ce qui court-circuiterait aussi le JWT
        # et rendrait ces tests inutiles (ils passeraient même avec un
        # mauvais token). On définit donc une clé API factice pour garder
        # auth_enabled=True, sans jamais l'envoyer dans les requêtes — ce
        # qui force bien la vérification JWT en isolation.
        os.environ["API_KEY"] = "unused-in-jwt-tests"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def test_bearer_token_grants_access(self):
        """JWT analyst valide → 200 sur /logs."""
        token = _make_jwt(role="analyst")
        response = self.client.get(
            "/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_rejected(self):
        """Token invalide → 401."""
        response = self.client.get(
            "/logs",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_viewer_cannot_analyze(self):
        """viewer → 403 sur /ollama/analyze-file (rôle insuffisant)."""
        token = _make_jwt(role="viewer")
        sample = (
            b"2026-06-18 10:00:00 ERROR Connection timeout\n"
        )
        response = self.client.post(
            "/ollama/analyze-file?max_errors=1",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.log", sample, "text/plain")},
        )
        self.assertEqual(response.status_code, 403)

    def test_analyst_can_analyze(self):
        """analyst → 200 sur /ollama/analyze-file (avec mock Ollama)."""
        from unittest.mock import AsyncMock, patch

        token = _make_jwt(role="analyst")
        sample = b"2026-06-18 10:00:00 ERROR Connection timeout\n"

        with patch("routers.ollama.analyze_with_ollama", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {
                "success": True,
                "analysis": {
                    "explanation": "Timeout.",
                    "causes": ["Réseau"],
                    "solutions": ["Redémarrer"],
                },
                "raw_response": "{}",
                "error": None,
            }
            response = self.client.post(
                "/ollama/analyze-file?max_errors=1",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test.log", sample, "text/plain")},
            )
        self.assertEqual(response.status_code, 200)

    def test_auth_register_and_login(self):
        """Flux complet : inscription → login → token valide.

        Note: get_password_hash/verify_password sont mockés pour éviter
        l'incompatibilité bcrypt>=4.0 / passlib 1.7.4 en Python 3.14.
        """
        from unittest.mock import patch

        _FAKE_HASH = "$2b$12$fakehashforunittestonly123456789"

        with patch("routers.auth.get_password_hash", return_value=_FAKE_HASH), \
             patch("routers.auth.verify_password", return_value=True):

            # Inscription
            reg = self.client.post(
                "/auth/register",
                json={
                    "email": "testuser@example.com",
                    "password": "Test1234",
                    "tenant_name": "Test Org",
                    "tenant_slug": "test-org",
                    "role": "analyst",
                },
            )
            self.assertIn(reg.status_code, (200, 201), msg=f"register failed: {reg.text}")
            self.assertIn("access_token", reg.json())

            # Login
            login = self.client.post(
                "/auth/login",
                json={
                    "email": "testuser@example.com",
                    "password": "Test1234",
                },
            )
            self.assertEqual(login.status_code, 200, msg=f"login failed: {login.text}")
            token = login.json()["access_token"]
            self.assertTrue(len(token) > 10)

        # Accès avec ce token (hors mock — JWT est réel)
        resp = self.client.get(
            "/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200)


class TestRequireRole(unittest.TestCase):
    """Tests directs pour core.security.require_role() — le cas
    'rôle insuffisant → 403' n'était jamais testé indépendamment d'un
    endpoint métier particulier."""

    @classmethod
    def setUpClass(cls):
        # Même remarque que TestJwtAuth : il faut auth_enabled=True (donc
        # API_KEY défini) pour que require_role() évalue réellement le rôle
        # porté par le JWT, plutôt que de bypasser l'auth entièrement.
        os.environ["API_KEY"] = "unused-in-role-tests"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def test_insufficient_role_returns_403(self):
        """/users (require_role(['admin'])) avec un rôle 'viewer' → 403."""
        token = _make_jwt(role="viewer")
        response = self.client.get(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Droit insuffisant", response.json()["detail"])

    def test_sufficient_role_is_allowed(self):
        """/users (require_role(['admin'])) avec un rôle 'admin' → 200."""
        token = _make_jwt(role="admin")
        response = self.client.get(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_missing_credentials_returns_401_not_403(self):
        """Sans credentials du tout, on doit avoir 401 (pas authentifié),
        pas 403 (authentifié mais rôle insuffisant) — les deux erreurs ont
        des causes différentes et ne doivent pas être confondues."""
        response = self.client.get("/users")
        self.assertEqual(response.status_code, 401)


class TestAuthRefresh(unittest.TestCase):
    """Tests pour l'endpoint POST /auth/refresh."""

    @classmethod
    def setUpClass(cls):
        os.environ["API_KEY"] = "unused-in-refresh-tests"
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_settings.cache_clear()

    def setUp(self):
        storage.init_db()
        self.client = TestClient(app)

    def _register_active_user(self, email: str) -> None:
        """Crée un utilisateur admin actif (premier utilisateur du tenant)
        pour obtenir un couple access/refresh token réel."""
        from unittest.mock import patch

        _FAKE_HASH = "$2b$12$fakehashforunittestonly123456789"
        with patch("routers.auth.get_password_hash", return_value=_FAKE_HASH):
            reg = self.client.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": "Test1234",
                    "tenant_name": "Refresh Org",
                    "tenant_slug": f"refresh-org-{email.split('@')[0]}",
                    "role": "admin",
                },
            )
        self.assertIn(reg.status_code, (200, 201), msg=reg.text)
        return reg.json()

    def test_register_returns_a_refresh_token(self):
        body = self._register_active_user("refresh-user1@example.com")
        self.assertIn("refresh_token", body)
        self.assertTrue(body["refresh_token"])

    def test_valid_refresh_token_issues_new_access_token(self):
        body = self._register_active_user("refresh-user2@example.com")
        response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": body["refresh_token"]},
        )
        self.assertEqual(response.status_code, 200, msg=response.text)
        new_body = response.json()
        self.assertIn("access_token", new_body)
        self.assertIn("refresh_token", new_body)
        self.assertTrue(len(new_body["access_token"]) > 10)

        # New access token must actually work on a protected route.
        resp = self.client.get(
            "/logs",
            headers={"Authorization": f"Bearer {new_body['access_token']}"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_refresh_rejects_an_access_token(self):
        """Un access token (type='access') ne doit pas être accepté comme
        refresh token — les deux types ne sont pas interchangeables."""
        body = self._register_active_user("refresh-user3@example.com")
        response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": body["access_token"]},
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_rejects_malformed_token(self):
        response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": "not.a.real.token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_rejects_suspended_account(self):
        """Si le compte est désactivé après l'émission du refresh token,
        le refresh doit être refusé immédiatement (mini révocation via
        re-vérification du statut en base, voir routers/auth.py)."""
        body = self._register_active_user("refresh-user4@example.com")
        me = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        ).json()

        storage.update_user_status(me["user_id"], "rejected")

        response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": body["refresh_token"]},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()