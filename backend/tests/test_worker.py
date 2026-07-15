"""
Tests pour les fonctions pures de worker.py.
Aucune connexion Redis ou Celery requise : on mocke les dépendances externes.
"""
from __future__ import annotations

import sys
import types
import time
import unittest
from unittest.mock import patch, MagicMock

# ── Stub celery avant l'import de worker ────────────────────────────────────
# worker.py fait `from celery import Celery` au niveau module.
# On stub celery pour qu'il soit importable sans installer le broker.
celery_stub = types.ModuleType("celery")

class _FakeConf:
    def update(self, **kw): pass

class _FakeCelery:
    def __init__(self, *a, **kw):
        self.conf = _FakeConf()
    def task(self, *a, **kw):
        def decorator(fn): return fn
        return decorator

celery_stub.Celery = _FakeCelery
sys.modules.setdefault("celery", celery_stub)

# Stub redis (used indirectly via job_store)
redis_stub = types.ModuleType("redis")
sys.modules.setdefault("redis", redis_stub)

# Stub services.storage
storage_stub = types.ModuleType("services.storage")
storage_stub.save_analysis = MagicMock(return_value=42)
storage_stub.get_cached_error_analysis = MagicMock(return_value=None)
sys.modules["services.storage"] = storage_stub

# Stub core.job_store
job_store_stub = types.ModuleType("core.job_store")
job_store_stub.update_job = MagicMock()
sys.modules["core.job_store"] = job_store_stub

# Stub services.ollama_service
ollama_stub = types.ModuleType("services.ollama_service")
ollama_stub.analyze_with_ollama = MagicMock()
sys.modules["services.ollama_service"] = ollama_stub

# Now import the pure helpers from worker
import importlib
import worker as w


# ── Helper : fake LogEntry ────────────────────────────────────────────────────
class FakeEntry:
    def __init__(self, message: str, level: str = "ERROR", timestamp: str = "2026-06-18 10:00:00",
                 line_number: int = 1):
        self.message = message
        self.level = level
        self.timestamp = timestamp
        self.line_number = line_number


# ── _empty_result_payload ─────────────────────────────────────────────────────
class TestEmptyResultPayload(unittest.TestCase):
    def test_returns_dict_with_correct_filename(self):
        result = w._empty_result_payload("server.log")
        self.assertEqual(result["filename"], "server.log")

    def test_total_errors_found_is_zero(self):
        result = w._empty_result_payload("x.log")
        self.assertEqual(result["total_errors_found"], 0)

    def test_total_analyzed_is_zero(self):
        result = w._empty_result_payload("x.log")
        self.assertEqual(result["total_analyzed"], 0)

    def test_analyzed_list_is_empty(self):
        result = w._empty_result_payload("x.log")
        self.assertEqual(result["analyzed"], [])

    def test_message_is_present(self):
        result = w._empty_result_payload("x.log")
        self.assertIn("message", result)
        self.assertTrue(len(result["message"]) > 0)


# ── _deduplicate_entries ──────────────────────────────────────────────────────
class TestDeduplicateEntries(unittest.TestCase):
    def test_single_unique_entry(self):
        entries = [FakeEntry("Connection timeout")]
        unique, occurrences = w._deduplicate_entries(entries)
        self.assertEqual(len(unique), 1)
        self.assertEqual(occurrences["Connection timeout"], 1)

    def test_duplicate_entries_are_merged(self):
        entries = [FakeEntry("DB error"), FakeEntry("DB error"), FakeEntry("DB error")]
        unique, occurrences = w._deduplicate_entries(entries)
        self.assertEqual(len(unique), 1)
        self.assertEqual(occurrences["DB error"], 3)

    def test_multiple_distinct_messages(self):
        entries = [FakeEntry("Err A"), FakeEntry("Err B"), FakeEntry("Err A")]
        unique, occurrences = w._deduplicate_entries(entries)
        self.assertEqual(len(unique), 2)
        self.assertEqual(occurrences["Err A"], 2)
        self.assertEqual(occurrences["Err B"], 1)

    def test_preserves_first_occurrence_entry(self):
        e1 = FakeEntry("dup", line_number=5)
        e2 = FakeEntry("dup", line_number=10)
        unique, _ = w._deduplicate_entries([e1, e2])
        self.assertEqual(unique["dup"].line_number, 5)

    def test_empty_list_returns_empty_dicts(self):
        unique, occurrences = w._deduplicate_entries([])
        self.assertEqual(unique, {})
        self.assertEqual(occurrences, {})


# ── _cached_analysis_result ───────────────────────────────────────────────────
class TestCachedAnalysisResult(unittest.TestCase):
    def setUp(self):
        storage_stub.get_cached_error_analysis.reset_mock()

    def test_returns_none_when_no_cache(self):
        storage_stub.get_cached_error_analysis.return_value = None
        result = w._cached_analysis_result("some error", "connection", time.time())
        self.assertIsNone(result)

    def test_returns_none_when_cache_has_no_explanation(self):
        storage_stub.get_cached_error_analysis.return_value = {"analysis": {}}
        result = w._cached_analysis_result("error msg", "database", time.time())
        self.assertIsNone(result)

    def test_returns_cached_result_when_valid(self):
        storage_stub.get_cached_error_analysis.return_value = {
            "category": "network",
            "analysis": {"explanation": "Le serveur est injoignable."},
        }
        result = w._cached_analysis_result("error msg", "connection", time.time())
        self.assertIsNotNone(result)
        self.assertEqual(result["message"], "error msg")
        self.assertTrue(result["success"])
        self.assertTrue(result["from_cache"])

    def test_cached_result_uses_stored_category_when_available(self):
        storage_stub.get_cached_error_analysis.return_value = {
            "category": "auth",
            "analysis": {"explanation": "Auth failed."},
        }
        result = w._cached_analysis_result("err", "connection", time.time())
        self.assertEqual(result["category"], "auth")

    def test_cached_result_falls_back_to_given_category_when_none(self):
        storage_stub.get_cached_error_analysis.return_value = {
            "category": None,
            "analysis": {"explanation": "Unknown error."},
        }
        result = w._cached_analysis_result("err", "disk", time.time())
        self.assertEqual(result["category"], "disk")

    def test_cached_result_has_processing_time(self):
        storage_stub.get_cached_error_analysis.return_value = {
            "analysis": {"explanation": "ok"},
        }
        start = time.time()
        result = w._cached_analysis_result("err", "ssl", start)
        self.assertIn("processing_time_seconds", result)
        self.assertGreaterEqual(result["processing_time_seconds"], 0)

    def test_rag_used_is_false_for_cached(self):
        storage_stub.get_cached_error_analysis.return_value = {
            "analysis": {"explanation": "ok"},
        }
        result = w._cached_analysis_result("err", "ssl", time.time())
        self.assertFalse(result["rag_used"])


# ── _build_results_list ───────────────────────────────────────────────────────
class TestBuildResultsList(unittest.TestCase):
    def _make_unique_results(self, messages: list[str]) -> dict:
        return {
            msg: {
                "category": "connection",
                "success": True,
                "analysis": {"explanation": "ok"},
                "error": None,
                "rag_used": False,
                "from_cache": True,
                "processing_time_seconds": 0.5,
            }
            for msg in messages
        }

    def test_output_length_matches_input(self):
        entries = [FakeEntry("E1"), FakeEntry("E2"), FakeEntry("E1")]
        unique_results = self._make_unique_results(["E1", "E2"])
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(len(result), 3)

    def test_index_is_one_based(self):
        entries = [FakeEntry("E1")]
        unique_results = self._make_unique_results(["E1"])
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(result[0]["index"], 1)

    def test_preserves_entry_order(self):
        entries = [FakeEntry("E2"), FakeEntry("E1")]
        unique_results = self._make_unique_results(["E1", "E2"])
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(result[0]["message"], "E2")
        self.assertEqual(result[1]["message"], "E1")

    def test_result_contains_line_number(self):
        entries = [FakeEntry("E1", line_number=42)]
        unique_results = self._make_unique_results(["E1"])
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(result[0]["line_number"], 42)

    def test_result_contains_level(self):
        entries = [FakeEntry("E1", level="CRITICAL")]
        unique_results = self._make_unique_results(["E1"])
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(result[0]["level"], "CRITICAL")

    def test_result_contains_category_from_unique_results(self):
        entries = [FakeEntry("E1")]
        unique_results = {"E1": {
            "category": "memory",
            "success": True,
            "analysis": None,
            "error": None,
            "rag_used": False,
            "from_cache": False,
            "processing_time_seconds": 1.0,
        }}
        result = w._build_results_list(entries, unique_results)
        self.assertEqual(result[0]["category"], "memory")

    def test_from_cache_field_is_present(self):
        entries = [FakeEntry("E1")]
        unique_results = self._make_unique_results(["E1"])
        result = w._build_results_list(entries, unique_results)
        self.assertIn("from_cache", result[0])

    def test_empty_entries_returns_empty_list(self):
        result = w._build_results_list([], {})
        self.assertEqual(result, [])


# ── _run_async ────────────────────────────────────────────────────────────────
class TestRunAsync(unittest.TestCase):
    def test_runs_simple_coroutine(self):
        import asyncio
        async def _coro():
            return 42
        result = w._run_async(_coro())
        self.assertEqual(result, 42)

    def test_runs_coroutine_with_await(self):
        import asyncio
        async def _coro():
            await asyncio.sleep(0)
            return "done"
        result = w._run_async(_coro())
        self.assertEqual(result, "done")

    def test_propagates_exceptions(self):
        import asyncio
        async def _bad():
            raise ValueError("boom")
        with self.assertRaises(ValueError):
            w._run_async(_bad())


if __name__ == "__main__":
    unittest.main()
