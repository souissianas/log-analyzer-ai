import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_orig_redis = sys.modules.get("redis")

# Inject a mock redis module into sys.modules to prevent ModuleNotFoundError
mock_redis_module = types.ModuleType("redis")
mock_redis_module.from_url = MagicMock()
sys.modules["redis"] = mock_redis_module

from core import job_store


class TestJobStore(unittest.TestCase):
    def setUp(self):
        # Reset local cache and mocks
        job_store._redis_client = None
        mock_redis_module.from_url.reset_mock()

    def tearDown(self):
        job_store._redis_client = None

    def test_get_redis_success(self):
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        
        # First call
        client = job_store._get_redis()
        self.assertEqual(client, mock_client)
        mock_redis_module.from_url.assert_called_once_with(job_store.REDIS_URL, decode_responses=True)
        mock_client.ping.assert_called_once()

        # Second call (uses cached client)
        client2 = job_store._get_redis()
        self.assertEqual(client2, mock_client)
        mock_redis_module.from_url.assert_called_once()  # No new call

    def test_get_redis_failure(self):
        mock_redis_module.from_url.side_effect = Exception("Redis connection refused")
        
        client = job_store._get_redis()
        self.assertIsNone(client)
        mock_redis_module.from_url.side_effect = None

    @patch("core.job_store._get_redis")
    def test_set_and_get_job_success(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        # Test set_job
        job_id = "test-job-1"
        test_data = {"status": "pending", "total": 100}
        job_store.set_job(job_id, test_data)
        
        mock_redis.setex.assert_called_once_with(
            "job:test-job-1",
            job_store.JOB_TTL_SECONDS,
            json.dumps(test_data, ensure_ascii=False)
        )

        # Test get_job
        mock_redis.get.return_value = json.dumps(test_data)
        result = job_store.get_job(job_id)
        
        self.assertEqual(result, test_data)
        mock_redis.get.assert_called_once_with("job:test-job-1")

    @patch("core.job_store._get_redis")
    def test_get_job_not_found(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None
        
        result = job_store.get_job("non-existent")
        self.assertIsNone(result)

    @patch("core.job_store._get_redis")
    def test_set_and_get_job_when_redis_is_none(self, mock_get_redis):
        mock_get_redis.return_value = None
        
        job_store.set_job("job-1", {"status": "ok"})
        result = job_store.get_job("job-1")
        self.assertIsNone(result)

    @patch("core.job_store._get_redis")
    def test_redis_methods_raise_exceptions_handled_gracefully(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.setex.side_effect = Exception("Write error")
        mock_redis.get.side_effect = Exception("Read error")

        # Shouldn't raise
        job_store.set_job("job-1", {})
        result = job_store.get_job("job-1")
        self.assertIsNone(result)

    @patch("core.job_store.get_job")
    @patch("core.job_store.set_job")
    def test_create_and_update_job(self, mock_set_job, mock_get_job):
        # Create
        job_id = "test-job-create"
        res = job_store.create_job(job_id, "file.txt", 50)
        
        self.assertEqual(res["job_id"], job_id)
        self.assertEqual(res["status"], "pending")
        self.assertEqual(res["total"], 50)
        mock_set_job.assert_called_once_with(job_id, res)

        # Update
        mock_get_job.return_value = res
        job_store.update_job(job_id, status="running", current=5)
        
        updated_data = res.copy()
        updated_data["status"] = "running"
        updated_data["current"] = 5
        mock_set_job.assert_called_with(job_id, updated_data)


def tearDownModule():
    # Restore original redis module to prevent side-effects in other tests
    if _orig_redis is None:
        sys.modules.pop("redis", None)
    else:
        sys.modules["redis"] = _orig_redis
