import os
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

# Configuration des variables d'environnement de test avant l'import
os.environ.setdefault("JWT_SECRET_KEY", "jwt-secret-key-for-testing-purposes-only")

from core import jwt


class TestJWTHelpers(unittest.TestCase):
    def test_password_hashing_and_verification_bcrypt_direct(self):
        password = "super-secret-password"
        hashed = jwt.get_password_hash(password)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))
        
        # Vérification correcte
        self.assertTrue(jwt.verify_password(password, hashed))
        # Mauvais mot de passe
        self.assertFalse(jwt.verify_password("wrong-password", hashed))

    @patch("core.jwt._bcrypt_lib", None)
    def test_password_hashing_and_verification_passlib_fallback(self):
        password = "fallback-test-password"
        # Si passlib est dispo, on l'utilise
        if jwt._USE_PASSLIB and jwt._pwd_context:
            hashed = jwt.get_password_hash(password)
            self.assertTrue(jwt.verify_password(password, hashed))
            self.assertFalse(jwt.verify_password("wrong", hashed))
        else:
            with self.assertRaises(RuntimeError):
                jwt.get_password_hash(password)

    @patch("core.jwt._bcrypt_lib")
    @patch("core.jwt._USE_PASSLIB", False)
    def test_password_hash_raises_when_no_library(self, mock_bcrypt):
        # bcrypt lib throws on hashpw, and passlib is disabled
        mock_bcrypt.hashpw.side_effect = Exception("Crash")
        with self.assertRaises(RuntimeError):
            jwt.get_password_hash("pass")

    @patch("core.jwt._bcrypt_lib")
    @patch("core.jwt._USE_PASSLIB", True)
    @patch("core.jwt._pwd_context")
    def test_verify_password_falls_back_when_bcrypt_fails(self, mock_pwd_context, mock_bcrypt):
        mock_bcrypt.checkpw.side_effect = Exception("Bcrypt Error")
        mock_pwd_context.verify.return_value = True
        
        res = jwt.verify_password("plain", "hashed")
        self.assertTrue(res)
        mock_pwd_context.verify.assert_called_once_with("plain", "hashed")

    @patch("core.jwt._bcrypt_lib", None)
    @patch("core.jwt._USE_PASSLIB", False)
    def test_verify_password_returns_false_when_no_lib(self):
        res = jwt.verify_password("plain", "hashed")
        self.assertFalse(res)

    def test_create_and_decode_access_token_success(self):
        data = {"sub": "user@example.com", "role": "analyst", "tenant_id": "tenant-1"}
        token = jwt.create_access_token(data, expires_delta=timedelta(minutes=15))
        
        # Simple decode
        payload = jwt.decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user@example.com")
        self.assertEqual(payload["role"], "analyst")
        self.assertEqual(payload["type"], "access")

        # Full decode
        payload_full, error = jwt.decode_token_full(token)
        self.assertIsNone(error)
        self.assertEqual(payload_full["sub"], "user@example.com")

    def test_decode_invalid_token_returns_error(self):
        payload, error = jwt.decode_token_full("this-is-not-a-valid-jwt-token")
        self.assertIsNone(payload)
        self.assertEqual(error, "invalid")

        payload_simple = jwt.decode_token("invalid-token")
        self.assertIsNone(payload_simple)

    def test_decode_expired_token_returns_expired_error(self):
        data = {"sub": "expired@test.com"}
        # Create token that expired 10 minutes ago
        token = jwt.create_access_token(data, expires_delta=timedelta(minutes=-10))
        
        payload, error = jwt.decode_token_full(token)
        self.assertIsNone(payload)
        self.assertEqual(error, "expired")

        payload_simple = jwt.decode_token(token)
        self.assertIsNone(payload_simple)

    def test_create_and_decode_refresh_token_success(self):
        data = {"sub": "user@test.com", "user_id": 123}
        token = jwt.create_refresh_token(data, expires_delta=timedelta(days=1))
        
        # Decode refresh token
        payload, error = jwt.decode_refresh_token(token)
        self.assertIsNone(error)
        self.assertEqual(payload["sub"], "user@test.com")
        self.assertEqual(payload["type"], "refresh")

    def test_decode_refresh_token_fails_with_access_token(self):
        # Create an access token instead of a refresh token
        access_token = jwt.create_access_token({"sub": "user@test.com"})
        
        # decode_refresh_token should fail with "invalid" because type is "access"
        payload, error = jwt.decode_refresh_token(access_token)
        self.assertIsNone(payload)
        self.assertEqual(error, "invalid")

    def test_decode_refresh_token_propagates_expired_or_invalid(self):
        # Expired refresh token
        expired_token = jwt.create_refresh_token({"sub": "user@test.com"}, expires_delta=timedelta(days=-1))
        payload, error = jwt.decode_refresh_token(expired_token)
        self.assertIsNone(payload)
        self.assertEqual(error, "expired")

        # Invalid token
        payload, error = jwt.decode_refresh_token("completely-invalid")
        self.assertIsNone(payload)
        self.assertEqual(error, "invalid")
