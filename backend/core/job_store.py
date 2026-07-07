"""
core/job_store.py
Redis-backed job state store for async Celery analysis jobs.

Each job has: status (pending/running/done/failed), progress, result, error.
All keys have a 2-hour TTL so Redis doesn't grow unbounded.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JOB_TTL_SECONDS = 7200  # 2 hours

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as redis_lib  # type: ignore
        _redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Redis not available — job store disabled", extra={"error": str(exc)})
        return None


def _key(job_id: str) -> str:
    return f"job:{job_id}"


def set_job(job_id: str, data: dict) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(_key(job_id), JOB_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
    except Exception as exc:
        logger.warning("set_job failed", extra={"job_id": job_id, "error": str(exc)})


def get_job(job_id: str) -> Optional[dict]:
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(_key(job_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("get_job failed", extra={"job_id": job_id, "error": str(exc)})
        return None


def update_job(job_id: str, **fields: Any) -> None:
    """Patch individual fields on an existing job record."""
    job = get_job(job_id) or {}
    job.update(fields)
    set_job(job_id, job)


def create_job(job_id: str, filename: str, total: int) -> dict:
    data = {
        "job_id": job_id,
        "status": "pending",
        "filename": filename,
        "total": total,
        "current": 0,
        "result": None,
        "error": None,
        "log_id": None,
    }
    set_job(job_id, data)
    return data
