"""Tests pour core/config.py — toutes les proprietes de Settings."""
import os
import unittest
import warnings

os.environ.pop("DATABASE_URL", None)
os.environ.pop("SQLITE_DB_PATH", None)


class TestSettings(unittest.TestCase):

    def setUp(self):
        from core.config import Settings
        self.Settings = Settings

    # api_key / auth_enabled
    def test_api_key_returns_none_when_not_set(self):
        os.environ.pop("API_KEY", None)
        s = self.Settings()
        self.assertIsNone(s.api_key)

    def test_api_key_returns_value_when_set(self):
        os.environ["API_KEY"] = "my-secret"
        try:
            s = self.Settings()
            self.assertEqual(s.api_key, "my-secret")
        finally:
            os.environ.pop("API_KEY", None)

    def test_auth_disabled_when_no_api_key(self):
        os.environ.pop("API_KEY", None)
        s = self.Settings()
        self.assertFalse(s.auth_enabled)

    def test_auth_enabled_when_api_key_set(self):
        os.environ["API_KEY"] = "some-key"
        try:
            s = self.Settings()
            self.assertTrue(s.auth_enabled)
        finally:
            os.environ.pop("API_KEY", None)

    # cors_origins
    def test_cors_origins_default(self):
        os.environ.pop("CORS_ORIGINS", None)
        s = self.Settings()
        origins = s.cors_origins
        self.assertIsInstance(origins, list)
        self.assertGreater(len(origins), 0)

    def test_cors_origins_custom(self):
        os.environ["CORS_ORIGINS"] = "http://app.example.com,https://admin.example.com"
        try:
            s = self.Settings()
            self.assertEqual(s.cors_origins, ["http://app.example.com", "https://admin.example.com"])
        finally:
            os.environ.pop("CORS_ORIGINS", None)

    def test_cors_origins_strips_whitespace(self):
        os.environ["CORS_ORIGINS"] = "  http://a.com , http://b.com  "
        try:
            s = self.Settings()
            self.assertIn("http://a.com", s.cors_origins)
            self.assertIn("http://b.com", s.cors_origins)
        finally:
            os.environ.pop("CORS_ORIGINS", None)

    # jwt_secret_key
    def test_jwt_secret_returns_key_when_set(self):
        os.environ["JWT_SECRET_KEY"] = "super-secret-key-for-test"
        try:
            s = self.Settings()
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                key = s.jwt_secret_key
            self.assertEqual(key, "super-secret-key-for-test")
            self.assertEqual(len(w), 0)
        finally:
            os.environ.pop("JWT_SECRET_KEY", None)

    def test_jwt_secret_warns_when_empty(self):
        os.environ["JWT_SECRET_KEY"] = ""
        try:
            s = self.Settings()
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                s.jwt_secret_key
            self.assertTrue(len(w) > 0)
            self.assertIn("RuntimeWarning", str(w[0].category.__name__))
        finally:
            os.environ.pop("JWT_SECRET_KEY", None)

    def test_jwt_algorithm_default(self):
        os.environ.pop("JWT_ALGORITHM", None)
        s = self.Settings()
        self.assertEqual(s.jwt_algorithm, "HS256")

    def test_jwt_algorithm_custom(self):
        os.environ["JWT_ALGORITHM"] = "RS256"
        try:
            s = self.Settings()
            self.assertEqual(s.jwt_algorithm, "RS256")
        finally:
            os.environ.pop("JWT_ALGORITHM", None)

    # SMTP properties
    def test_smtp_host_returns_none_when_not_set(self):
        os.environ.pop("SMTP_HOST", None)
        s = self.Settings()
        self.assertIsNone(s.smtp_host)

    def test_smtp_host_strips_whitespace(self):
        os.environ["SMTP_HOST"] = "  smtp.gmail.com  "
        try:
            s = self.Settings()
            self.assertEqual(s.smtp_host, "smtp.gmail.com")
        finally:
            os.environ.pop("SMTP_HOST", None)

    def test_smtp_port_default(self):
        os.environ.pop("SMTP_PORT", None)
        s = self.Settings()
        self.assertEqual(s.smtp_port, 587)

    def test_smtp_port_custom(self):
        os.environ["SMTP_PORT"] = "465"
        try:
            s = self.Settings()
            self.assertEqual(s.smtp_port, 465)
        finally:
            os.environ.pop("SMTP_PORT", None)

    def test_smtp_port_invalid_falls_back_to_default(self):
        os.environ["SMTP_PORT"] = "not-a-number"
        try:
            s = self.Settings()
            self.assertEqual(s.smtp_port, 587)
        finally:
            os.environ.pop("SMTP_PORT", None)

    def test_smtp_user_returns_none_when_not_set(self):
        os.environ.pop("SMTP_USER", None)
        s = self.Settings()
        self.assertIsNone(s.smtp_user)

    def test_smtp_password_returns_none_when_not_set(self):
        os.environ.pop("SMTP_PASSWORD", None)
        s = self.Settings()
        self.assertIsNone(s.smtp_password)

    def test_smtp_sender_returns_none_when_not_set(self):
        os.environ.pop("SMTP_SENDER", None)
        s = self.Settings()
        self.assertIsNone(s.smtp_sender)

    def test_smtp_sender_strips_whitespace(self):
        os.environ["SMTP_SENDER"] = "  no-reply@example.com  "
        try:
            s = self.Settings()
            self.assertEqual(s.smtp_sender, "no-reply@example.com")
        finally:
            os.environ.pop("SMTP_SENDER", None)

    def test_smtp_enabled_false_when_missing_host(self):
        os.environ.pop("SMTP_HOST", None)
        os.environ["SMTP_SENDER"] = "sender@example.com"
        try:
            s = self.Settings()
            self.assertFalse(s.smtp_enabled)
        finally:
            os.environ.pop("SMTP_SENDER", None)

    def test_smtp_enabled_false_when_missing_sender(self):
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ.pop("SMTP_SENDER", None)
        try:
            s = self.Settings()
            self.assertFalse(s.smtp_enabled)
        finally:
            os.environ.pop("SMTP_HOST", None)

    def test_smtp_enabled_true_when_both_set(self):
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_SENDER"] = "no-reply@example.com"
        try:
            s = self.Settings()
            self.assertTrue(s.smtp_enabled)
        finally:
            os.environ.pop("SMTP_HOST", None)
            os.environ.pop("SMTP_SENDER", None)

    # get_settings lru_cache
    def test_get_settings_returns_settings_instance(self):
        from core.config import get_settings, Settings
        get_settings.cache_clear()
        s = get_settings()
        self.assertIsInstance(s, Settings)

    def test_get_settings_is_cached(self):
        from core.config import get_settings
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)


if __name__ == "__main__":
    unittest.main()
