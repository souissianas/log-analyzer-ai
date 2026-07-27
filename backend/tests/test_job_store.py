import json
import sys
import types
import pytest
from unittest.mock import MagicMock, patch

_orig_redis = sys.modules.get("redis")

mock_redis_module = types.ModuleType("redis")
mock_redis_module.from_url = MagicMock()
sys.modules["redis"] = mock_redis_module

from core import job_store


@pytest.fixture(autouse=True)
def reset_job_store_state(monkeypatch):
    monkeypatch.setattr(job_store, "_redis_client", None)
    mock_redis_module.from_url.reset_mock()
    mock_redis_module.from_url.side_effect = None


def test_get_redis_success():
    mock_client = MagicMock()
    mock_redis_module.from_url.return_value = mock_client
    
    client = job_store._get_redis()
    assert client == mock_client
    mock_redis_module.from_url.assert_called_once_with(job_store.REDIS_URL, decode_responses=True)
    mock_client.ping.assert_called_once()

    # Second call (uses cached client)
    client2 = job_store._get_redis()
    assert client2 == mock_client
    mock_redis_module.from_url.assert_called_once()


def test_get_redis_failure():
    mock_redis_module.from_url.side_effect = Exception("Redis connection refused")
    client = job_store._get_redis()
    assert client is None


@patch("core.job_store._get_redis")
def test_set_and_get_job_success(mock_get_redis):
    mock_redis = MagicMock()
    mock_get_redis.return_value = mock_redis
    
    job_id = "test-job-1"
    test_data = {"status": "pending", "total": 100}
    job_store.set_job(job_id, test_data)
    
    mock_redis.setex.assert_called_once_with(
        "job:test-job-1",
        job_store.JOB_TTL_SECONDS,
        json.dumps(test_data, ensure_ascii=False)
    )

    mock_redis.get.return_value = json.dumps(test_data)
    result = job_store.get_job(job_id)
    
    assert result == test_data
    mock_redis.get.assert_called_once_with("job:test-job-1")


@patch("core.job_store._get_redis")
def test_get_job_not_found(mock_get_redis):
    mock_redis = MagicMock()
    mock_get_redis.return_value = mock_redis
    mock_redis.get.return_value = None
    
    result = job_store.get_job("non-existent")
    assert result is None


@patch("core.job_store._get_redis")
def test_set_and_get_job_when_redis_is_none(mock_get_redis):
    mock_get_redis.return_value = None
    
    job_store.set_job("job-1", {"status": "ok"})
    result = job_store.get_job("job-1")
    assert result is None


@patch("core.job_store._get_redis")
def test_redis_methods_raise_exceptions_handled_gracefully(mock_get_redis):
    mock_redis = MagicMock()
    mock_get_redis.return_value = mock_redis
    mock_redis.setex.side_effect = Exception("Write error")
    mock_redis.get.side_effect = Exception("Read error")

    job_store.set_job("job-1", {})
    result = job_store.get_job("job-1")
    assert result is None


@patch("core.job_store.get_job")
@patch("core.job_store.set_job")
def test_create_and_update_job(mock_set_job, mock_get_job):
    job_id = "test-job-create"
    res = job_store.create_job(job_id, "file.txt", 50)
    
    assert res["job_id"] == job_id
    assert res["status"] == "pending"
    assert res["total"] == 50
    mock_set_job.assert_called_once_with(job_id, res)

    mock_get_job.return_value = res
    job_store.update_job(job_id, status="running", current=5)
    
    updated_data = res.copy()
    updated_data["status"] = "running"
    updated_data["current"] = 5
    mock_set_job.assert_called_with(job_id, updated_data)
