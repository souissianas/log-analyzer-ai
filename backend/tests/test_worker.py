"""
Tests pour les fonctions pures de worker.py.
Aucune connexion Redis ou Celery requise : on mocke les dépendances externes.
"""
from __future__ import annotations

import sys
import types
import time
import pytest
from unittest.mock import patch, MagicMock

_orig_celery = sys.modules.get("celery")
_orig_redis = sys.modules.get("redis")
_orig_storage = sys.modules.get("services.storage")
_orig_job_store = sys.modules.get("core.job_store")
_orig_ollama = sys.modules.get("services.ollama_service")

# ── Stub celery avant l'import de worker ────────────────────────────────────
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
sys.modules["celery"] = celery_stub

redis_stub = types.ModuleType("redis")
sys.modules["redis"] = redis_stub

storage_stub = types.ModuleType("services.storage")
storage_stub.save_analysis = MagicMock(return_value=42)
storage_stub.get_cached_error_analysis = MagicMock(return_value=None)
sys.modules["services.storage"] = storage_stub

job_store_stub = types.ModuleType("core.job_store")
job_store_stub.update_job = MagicMock()
sys.modules["core.job_store"] = job_store_stub

ollama_stub = types.ModuleType("services.ollama_service")
ollama_stub.analyze_with_ollama = MagicMock()
sys.modules["services.ollama_service"] = ollama_stub

import importlib
import worker as w

for modname, orig_val in [
    ("celery", _orig_celery),
    ("redis", _orig_redis),
    ("services.storage", _orig_storage),
    ("core.job_store", _orig_job_store),
    ("services.ollama_service", _orig_ollama),
]:
    if orig_val is None:
        sys.modules.pop(modname, None)
    else:
        sys.modules[modname] = orig_val


class FakeEntry:
    def __init__(self, message: str, level: str = "ERROR", timestamp: str = "2026-06-18 10:00:00",
                 line_number: int = 1):
        self.message = message
        self.level = level
        self.timestamp = timestamp
        self.line_number = line_number


@pytest.fixture(autouse=True)
def reset_storage_mocks(monkeypatch):
    monkeypatch.setattr(w.storage, "save_analysis", MagicMock(return_value=42))
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value=None))


# ── _empty_result_payload ─────────────────────────────────────────────────────
def test_returns_dict_with_correct_filename():
    result = w._empty_result_payload("server.log")
    assert result["filename"] == "server.log"


def test_total_errors_found_is_zero():
    result = w._empty_result_payload("x.log")
    assert result["total_errors_found"] == 0


def test_total_analyzed_is_zero():
    result = w._empty_result_payload("x.log")
    assert result["total_analyzed"] == 0


def test_analyzed_list_is_empty():
    result = w._empty_result_payload("x.log")
    assert result["analyzed"] == []


def test_message_is_present():
    result = w._empty_result_payload("x.log")
    assert "message" in result
    assert len(result["message"]) > 0


# ── _deduplicate_entries ──────────────────────────────────────────────────────
def test_single_unique_entry():
    entries = [FakeEntry("Connection timeout")]
    unique, occurrences = w._deduplicate_entries(entries)
    assert len(unique) == 1
    assert occurrences["Connection timeout"] == 1


def test_duplicate_entries_are_merged():
    entries = [FakeEntry("DB error"), FakeEntry("DB error"), FakeEntry("DB error")]
    unique, occurrences = w._deduplicate_entries(entries)
    assert len(unique) == 1
    assert occurrences["DB error"] == 3


def test_multiple_distinct_messages():
    entries = [FakeEntry("Err A"), FakeEntry("Err B"), FakeEntry("Err A")]
    unique, occurrences = w._deduplicate_entries(entries)
    assert len(unique) == 2
    assert occurrences["Err A"] == 2
    assert occurrences["Err B"] == 1


def test_preserves_first_occurrence_entry():
    e1 = FakeEntry("dup", line_number=5)
    e2 = FakeEntry("dup", line_number=10)
    unique, _ = w._deduplicate_entries([e1, e2])
    assert unique["dup"].line_number == 5


def test_empty_list_returns_empty_dicts():
    unique, occurrences = w._deduplicate_entries([])
    assert unique == {}
    assert occurrences == {}


# ── _cached_analysis_result ───────────────────────────────────────────────────
def test_returns_none_when_no_cache(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value=None))
    result = w._cached_analysis_result("some error", "connection", time.time())
    assert result is None


def test_returns_none_when_cache_has_no_explanation(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={"analysis": {}}))
    result = w._cached_analysis_result("error msg", "database", time.time())
    assert result is None


def test_returns_cached_result_when_valid(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={
        "category": "network",
        "analysis": {"explanation": "Le serveur est injoignable."},
    }))
    result = w._cached_analysis_result("error msg", "connection", time.time())
    assert result is not None
    assert result["message"] == "error msg"
    assert result["success"] is True
    assert result["from_cache"] is True


def test_cached_result_uses_stored_category_when_available(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={
        "category": "auth",
        "analysis": {"explanation": "Auth failed."},
    }))
    result = w._cached_analysis_result("err", "connection", time.time())
    assert result["category"] == "auth"


def test_cached_result_falls_back_to_given_category_when_none(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={
        "category": None,
        "analysis": {"explanation": "Unknown error."},
    }))
    result = w._cached_analysis_result("err", "disk", time.time())
    assert result["category"] == "disk"


def test_cached_result_has_processing_time(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={
        "analysis": {"explanation": "ok"},
    }))
    start = time.time()
    result = w._cached_analysis_result("err", "ssl", start)
    assert "processing_time_seconds" in result
    assert result["processing_time_seconds"] >= 0


def test_rag_used_is_false_for_cached(monkeypatch):
    monkeypatch.setattr(w, "get_cached_error_analysis", MagicMock(return_value={
        "analysis": {"explanation": "ok"},
    }))
    result = w._cached_analysis_result("err", "ssl", time.time())
    assert result["rag_used"] is False


# ── _build_results_list ───────────────────────────────────────────────────────
def _make_unique_results(messages: list[str]) -> dict:
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


def test_output_length_matches_input():
    entries = [FakeEntry("E1"), FakeEntry("E2"), FakeEntry("E1")]
    unique_results = _make_unique_results(["E1", "E2"])
    result = w._build_results_list(entries, unique_results)
    assert len(result) == 3


def test_index_is_one_based():
    entries = [FakeEntry("E1")]
    unique_results = _make_unique_results(["E1"])
    result = w._build_results_list(entries, unique_results)
    assert result[0]["index"] == 1


def test_preserves_entry_order():
    entries = [FakeEntry("E2"), FakeEntry("E1")]
    unique_results = _make_unique_results(["E1", "E2"])
    result = w._build_results_list(entries, unique_results)
    assert result[0]["message"] == "E2"
    assert result[1]["message"] == "E1"


def test_result_contains_line_number():
    entries = [FakeEntry("E1", line_number=42)]
    unique_results = _make_unique_results(["E1"])
    result = w._build_results_list(entries, unique_results)
    assert result[0]["line_number"] == 42


def test_result_contains_level():
    entries = [FakeEntry("E1", level="CRITICAL")]
    unique_results = _make_unique_results(["E1"])
    result = w._build_results_list(entries, unique_results)
    assert result[0]["level"] == "CRITICAL"


def test_result_contains_category_from_unique_results():
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
    assert result[0]["category"] == "memory"


def test_from_cache_field_is_present():
    entries = [FakeEntry("E1")]
    unique_results = _make_unique_results(["E1"])
    result = w._build_results_list(entries, unique_results)
    assert "from_cache" in result[0]


def test_empty_entries_returns_empty_list():
    result = w._build_results_list([], {})
    assert result == []


# ── _save_analysis_safe ────────────────────────────────────────────────────────
def test_save_success():
    with patch("worker.storage.save_analysis", return_value=100) as mock_save:
        res = w._save_analysis_safe({"data": "x"}, tenant_id=1, user_id=2)
        assert res == 100
        mock_save.assert_called_once_with({"data": "x"}, tenant_id=1, user_id=2)


def test_save_raises_exception_returns_none():
    with patch("worker.storage.save_analysis", side_effect=ValueError("DB Error")):
        res = w._save_analysis_safe({"data": "x"}, tenant_id=1, user_id=2)
        assert res is None


# ── _analyze_unique_entry & _analyze_entries ──────────────────────────────────
def test_analyze_unique_entry_cache_hit():
    with patch("worker.classify_error", return_value="database"), \
         patch("worker._cached_analysis_result", return_value={"from_cache": True, "category": "database"}), \
         patch("worker.analyze_with_ollama") as mock_analyze:
        entry = FakeEntry("pg connection failed")
        res = w._run_async(w._analyze_unique_entry("pg connection failed", entry))
        assert res["from_cache"] is True
        mock_analyze.assert_not_called()


def test_analyze_unique_entry_cache_miss():
    async def mock_coro(*args, **kwargs):
        return {"success": True, "analysis": "Detailed analysis", "error": None, "rag_used": False}

    with patch("worker.classify_error", return_value="database"), \
         patch("worker._cached_analysis_result", return_value=None), \
         patch("worker.analyze_with_ollama", side_effect=mock_coro) as mock_analyze:
        entry = FakeEntry("pg connection failed")
        res = w._run_async(w._analyze_unique_entry("pg connection failed", entry))
        assert res["from_cache"] is False
        assert res["analysis"] == "Detailed analysis"
        mock_analyze.assert_called_once()


def test_analyze_entries():
    with patch("worker._deduplicate_entries", return_value=({"msg": "entry"}, {"msg": 1})), \
         patch("worker._run_unique_analyses", return_value={"msg": {"category": "database"}}), \
         patch("worker._build_results_list", return_value=[{"index": 1}]):
        res = w._run_async(w._analyze_entries("job-123", ["entry"], 1))
        assert res == [{"index": 1}]


# ── analyze_file_task ──────────────────────────────────────────────────────────
def test_empty_log_content():
    with patch("worker.update_job") as mock_update_job, \
         patch("worker.parse_log_file", return_value=[]), \
         patch("worker.storage.save_analysis", return_value=500):
        res = w.analyze_file_task(None, "job-1", "", "empty.log", max_errors=5)
        assert res["filename"] == "empty.log"
        assert res["total_analyzed"] == 0
        
        called = any(
            args == ("job-1",) and kwargs.get("status") == "done" and kwargs.get("log_id") == 500 and kwargs.get("current") == 0
            for args, kwargs in mock_update_job.call_args_list
        )
        assert called is True


def test_nominal_flow():
    entries = [FakeEntry("Error 1"), FakeEntry("Error 2")]
    async def mock_coro(*args, **kwargs):
        return [
            {"index": 1, "message": "Error 1", "category": "database", "success": True, "analysis": "ok", "error": None, "rag_used": False, "processing_time_seconds": 0.5}
        ]

    with patch("worker.update_job") as mock_update_job, \
         patch("worker.parse_log_file", return_value=entries), \
         patch("worker._analyze_entries", side_effect=mock_coro), \
         patch("worker._save_analysis_safe", return_value=600):
        res = w.analyze_file_task(None, "job-2", "content", "app.log", max_errors=1)
        assert res["filename"] == "app.log"
        assert res["total_errors_found"] == 2
        assert res["total_analyzed"] == 1
        assert res["skipped"] == 1
        mock_update_job.assert_any_call("job-2", status="done", result=res, log_id=600)


def test_exception_handling():
    with patch("worker.update_job") as mock_update_job, \
         patch("worker.parse_log_file", side_effect=ValueError("Parsing crash")):
        with pytest.raises(ValueError, match="Parsing crash"):
            w.analyze_file_task(None, "job-3", "corrupted", "app.log")
        mock_update_job.assert_any_call("job-3", status="failed", error="Parsing crash")


# ── _run_async ────────────────────────────────────────────────────────────────
def test_runs_simple_coroutine():
    async def _coro():
        return 42
    result = w._run_async(_coro())
    assert result == 42


def test_runs_coroutine_with_await():
    import asyncio
    async def _coro():
        await asyncio.sleep(0)
        return "done"
    result = w._run_async(_coro())
    assert result == "done"


def test_propagates_exceptions():
    async def _bad():
        raise ValueError("boom")
    with pytest.raises(ValueError, match="boom"):
        w._run_async(_bad())
