"""
Tests for services/storage.py — covers functions not exercised by other test files.
Uses a dedicated in-memory / temp-file SQLite DB; never touches PostgreSQL.
"""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# ── Ensure SQLite path is isolated ──────────────────────────────────────────
os.environ.pop("DATABASE_URL", None)
_fd, _DB_PATH = tempfile.mkstemp(suffix="_storage_test.db")
os.close(_fd)
os.environ["SQLITE_DB_PATH"] = _DB_PATH

import importlib
import services.storage as storage

importlib.reload(storage)
storage.SQLITE_DB_PATH = _DB_PATH


def _setup():
    """Re-init DB tables in the test database."""
    storage.init_db()


# ─────────────────────────────────────────────────────────────────────────────
# check_db_health
# ─────────────────────────────────────────────────────────────────────────────
class TestCheckDbHealth(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_returns_ok_true_for_sqlite(self):
        result = storage.check_db_health()
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "sqlite")

    def test_returns_ok_false_on_error(self):
        with patch("services.storage._get_sqlite_connection", side_effect=Exception("no db")):
            result = storage.check_db_health()
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ─────────────────────────────────────────────────────────────────────────────
# OTP functions
# ─────────────────────────────────────────────────────────────────────────────
class TestOtpFunctions(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_save_and_get_otp(self):
        expires = time.time() + 300
        storage.save_otp("test@example.com", "123456", expires)
        result = storage.get_otp("test@example.com")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "123456")
        self.assertAlmostEqual(result["expires"], expires, places=0)

    def test_get_otp_returns_none_when_missing(self):
        result = storage.get_otp("nobody@example.com")
        self.assertIsNone(result)

    def test_delete_otp(self):
        storage.save_otp("del@example.com", "999999", time.time() + 60)
        storage.delete_otp("del@example.com")
        result = storage.get_otp("del@example.com")
        self.assertIsNone(result)

    def test_save_otp_overwrites_existing(self):
        storage.save_otp("ow@example.com", "111111", time.time() + 60)
        storage.save_otp("ow@example.com", "222222", time.time() + 120)
        result = storage.get_otp("ow@example.com")
        self.assertEqual(result["code"], "222222")


# ─────────────────────────────────────────────────────────────────────────────
# Tenant functions
# ─────────────────────────────────────────────────────────────────────────────
class TestTenantFunctions(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_create_and_get_tenant(self):
        tenant_id = storage.create_tenant("Acme Corp", "acme-corp")
        self.assertIsNotNone(tenant_id)
        tenant = storage.get_tenant_by_slug("acme-corp")
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant["name"], "Acme Corp")
        self.assertEqual(tenant["slug"], "acme-corp")

    def test_get_tenant_by_slug_returns_none_when_missing(self):
        result = storage.get_tenant_by_slug("nonexistent-slug-xyz")
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# User management functions
# ─────────────────────────────────────────────────────────────────────────────
class TestUserFunctions(unittest.TestCase):
    def setUp(self):
        _setup()
        self._tenant_id = storage.create_tenant("Test Org", f"test-org-{int(time.time() * 1000)}")

    def _create_user(self, email="u@example.com", role="viewer", status="active"):
        return storage.create_user(self._tenant_id, email, role, "hashed_pw", status)

    def test_create_and_get_user_by_email(self):
        self._create_user("user1@example.com")
        user = storage.get_user_by_email("user1@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "user1@example.com")

    def test_get_user_by_email_returns_none_when_missing(self):
        result = storage.get_user_by_email("ghost@example.com")
        self.assertIsNone(result)

    def test_get_user_by_id(self):
        uid = self._create_user("user2@example.com")
        user = storage.get_user_by_id(uid)
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], uid)

    def test_get_user_by_id_returns_none_when_missing(self):
        result = storage.get_user_by_id(999999)
        self.assertIsNone(result)

    def test_list_users_without_tenant(self):
        self._create_user("list1@example.com")
        users = storage.list_users()
        self.assertIsInstance(users, list)
        emails = [u["email"] for u in users]
        self.assertIn("list1@example.com", emails)

    def test_list_users_with_tenant(self):
        uid = self._create_user("tenant_user@example.com")
        users = storage.list_users(tenant_id=self._tenant_id)
        self.assertTrue(any(u["email"] == "tenant_user@example.com" for u in users))

    def test_update_user_status_valid(self):
        uid = self._create_user("status_user@example.com")
        result = storage.update_user_status(uid, "active")
        self.assertTrue(result)

    def test_update_user_status_invalid_returns_false(self):
        uid = self._create_user("bad_status@example.com")
        result = storage.update_user_status(uid, "superadmin")
        self.assertFalse(result)

    def test_update_user_role_valid(self):
        uid = self._create_user("role_user@example.com")
        result = storage.update_user_role(uid, "admin")
        self.assertTrue(result)

    def test_update_user_role_invalid_returns_false(self):
        uid = self._create_user("bad_role@example.com")
        result = storage.update_user_role(uid, "superadmin")
        self.assertFalse(result)

    def test_delete_user(self):
        uid = self._create_user("delete_me@example.com")
        result = storage.delete_user(uid)
        self.assertTrue(result)
        self.assertIsNone(storage.get_user_by_id(uid))

    def test_update_user_password(self):
        self._create_user("pw_user@example.com")
        result = storage.update_user_password("pw_user@example.com", "new_hashed_pw")
        self.assertTrue(result)

    def test_count_users_by_tenant(self):
        self._create_user(f"count1_{int(time.time()*1000)}@example.com")
        self._create_user(f"count2_{int(time.time()*1000)}@example.com")
        count = storage.count_users_by_tenant(self._tenant_id)
        self.assertGreaterEqual(count, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────────────────────────────────────
class TestDashboardStats(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_get_dashboard_stats_returns_expected_keys(self):
        stats = storage.get_dashboard_stats()
        for key in ("total_analyses", "total_errors", "total_analyzed",
                    "errors_by_level", "analyses_per_day", "top_files", "errors_by_category"):
            self.assertIn(key, stats)

    def test_get_dashboard_stats_with_tenant_id(self):
        stats = storage.get_dashboard_stats(tenant_id=999)
        self.assertIsInstance(stats["total_analyses"], int)
        self.assertIsInstance(stats["errors_by_level"], dict)
        self.assertIsInstance(stats["analyses_per_day"], list)

    def test_total_analyses_increases_after_save(self):
        before = storage.get_dashboard_stats()["total_analyses"]
        storage.save_analysis({
            "filename": "dash_test.log",
            "total_errors_found": 1,
            "total_analyzed": 1,
            "analyzed": [],
        })
        after = storage.get_dashboard_stats()["total_analyses"]
        self.assertGreater(after, before)


# ─────────────────────────────────────────────────────────────────────────────
# count_analyses
# ─────────────────────────────────────────────────────────────────────────────
class TestCountAnalyses(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_count_without_tenant(self):
        before = storage.count_analyses()
        storage.save_analysis({
            "filename": "count_test.log",
            "total_errors_found": 0,
            "total_analyzed": 0,
            "analyzed": [],
        })
        after = storage.count_analyses()
        self.assertEqual(after, before + 1)

    def test_count_with_unknown_tenant_returns_zero(self):
        count = storage.count_analyses(tenant_id=888888)
        self.assertEqual(count, 0)


# ─────────────────────────────────────────────────────────────────────────────
# get_cached_error_analysis
# ─────────────────────────────────────────────────────────────────────────────
class TestGetCachedErrorAnalysis(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_returns_none_when_no_match(self):
        result = storage.get_cached_error_analysis("totally unknown error xyz")
        self.assertIsNone(result)

    def test_returns_cached_result_after_save(self):
        # Save an analysis with an error to populate analysis_errors table
        storage.save_analysis({
            "filename": "cache_test.log",
            "total_errors_found": 1,
            "total_analyzed": 1,
            "analyzed": [
                {
                    "line_number": 1,
                    "level": "ERROR",
                    "message": "Cache test error XYZ-unique",
                    "category": "connection",
                    "analysis": {
                        "explanation": "Test explanation",
                        "causes": ["cause1"],
                        "solutions": ["solution1"],
                    },
                }
            ],
        })
        result = storage.get_cached_error_analysis("Cache test error XYZ-unique")
        self.assertIsNotNone(result)
        self.assertIn("analysis", result)
        self.assertEqual(result["analysis"]["explanation"], "Test explanation")

    def test_causes_and_solutions_parsed_from_json_string(self):
        """If causes/solutions are stored as JSON strings, they must be deserialized."""
        storage.save_analysis({
            "filename": "json_cache.log",
            "total_errors_found": 1,
            "total_analyzed": 1,
            "analyzed": [
                {
                    "line_number": 2,
                    "level": "ERROR",
                    "message": "JSON causes test error UNIQUE-789",
                    "category": "disk",
                    "analysis": {
                        "explanation": "Disk full",
                        "causes": ["Not enough space"],
                        "solutions": ["Free up disk"],
                    },
                }
            ],
        })
        result = storage.get_cached_error_analysis("JSON causes test error UNIQUE-789")
        self.assertIsNotNone(result)
        causes = result["analysis"]["causes"]
        self.assertIsInstance(causes, list)


# ─────────────────────────────────────────────────────────────────────────────
# list_analyses / get_analysis / save_analysis
# ─────────────────────────────────────────────────────────────────────────────
class TestAnalysisCrud(unittest.TestCase):
    def setUp(self):
        _setup()

    def test_save_returns_integer_id(self):
        aid = storage.save_analysis({
            "filename": "crud.log",
            "total_errors_found": 0,
            "total_analyzed": 0,
            "analyzed": [],
        })
        self.assertIsInstance(aid, int)
        self.assertGreater(aid, 0)

    def test_get_analysis_returns_saved(self):
        aid = storage.save_analysis({
            "filename": "get_test.log",
            "total_errors_found": 1,
            "total_analyzed": 1,
            "analyzed": [],
        })
        row = storage.get_analysis(aid)
        self.assertIsNotNone(row)
        self.assertEqual(row["filename"], "get_test.log")

    def test_get_analysis_returns_none_for_missing(self):
        result = storage.get_analysis(999999)
        self.assertIsNone(result)

    def test_list_analyses_returns_list(self):
        storage.save_analysis({
            "filename": "list_test.log",
            "total_errors_found": 0,
            "total_analyzed": 0,
            "analyzed": [],
        })
        rows = storage.list_analyses(limit=10)
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_list_analyses_with_tenant_filter(self):
        rows = storage.list_analyses(tenant_id=777)
        self.assertIsInstance(rows, list)

    def test_save_analysis_with_errors_populates_analysis_errors(self):
        aid = storage.save_analysis({
            "filename": "with_errors.log",
            "total_errors_found": 2,
            "total_analyzed": 2,
            "analyzed": [
                {
                    "line_number": 10,
                    "level": "ERROR",
                    "message": "err msg A",
                    "category": "memory",
                    "analysis": {
                        "explanation": "Memory leak",
                        "causes": ["Heap overflow"],
                        "solutions": ["Restart service"],
                    },
                },
                {
                    "line_number": 20,
                    "level": "CRITICAL",
                    "message": "err msg B",
                    "category": "disk",
                    "analysis": {
                        "explanation": "Disk full",
                        "causes": ["Logs not rotated"],
                        "solutions": ["Run logrotate"],
                    },
                },
            ],
        })
        self.assertIsInstance(aid, int)


if __name__ == "__main__":
    unittest.main()
