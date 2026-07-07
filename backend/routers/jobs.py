"""
routers/jobs.py
Async analysis job endpoints (Celery + Redis + SSE).

POST  /jobs/analyze          — submit file, returns job_id immediately
GET   /jobs/{job_id}/status  — poll job status + progress
GET   /jobs/{job_id}/stream  — Server-Sent Events (real-time progress)
GET   /jobs/{job_id}/result  — full result when done
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from core.job_store import create_job, get_job
from core.security import get_current_user_or_api_key
from core.upload import decode_upload, read_upload_with_limit, validate_log_extension

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_celery():
    """Lazy import to avoid loading Celery when it is not installed."""
    try:
        from worker import analyze_file_task  # type: ignore
        return analyze_file_task
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Celery worker unavailable: {exc}")


@router.post("/analyze", summary="Submit async analysis job")
async def submit_analysis_job(
    file: UploadFile = File(...),
    max_errors: int = 5,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    """
    Upload a log file. Returns a job_id immediately.
    Use /jobs/{job_id}/stream for real-time SSE progress,
    or /jobs/{job_id}/status for polling.
    """
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Droit insuffisant pour soumettre une analyse")
        
    validate_log_extension(file.filename)
    content_bytes = await read_upload_with_limit(file)
    content = decode_upload(content_bytes)

    job_id = str(uuid.uuid4())
    # Count lines to give the frontend a total estimate
    line_count = content.count("\n") + 1
    create_job(job_id, filename=file.filename or "upload.log", total=min(line_count, max_errors))

    tenant_id = current_user.get("tenant_id")
    user_id = current_user.get("user_id")

    task_fn = _get_celery()
    task_fn.apply_async(
        args=[job_id, content, file.filename or "upload.log", max_errors, tenant_id, user_id],
        task_id=job_id,
    )

    logger.info("Job submitted", extra={"job_id": job_id, "log_filename": file.filename, "tenant_id": tenant_id})
    return {"job_id": job_id, "status": "pending", "filename": file.filename}


@router.get("/{job_id}/status", summary="Poll job status")
@router.get("/{job_id}", summary="Poll job status (alias)")
def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    """Returns current status + progress counter. Safe to poll every second."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    # Strip large result from status endpoint
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "filename": job.get("filename"),
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "log_id": job.get("log_id"),
        "error": job.get("error"),
    }


@router.get("/{job_id}/stream", summary="Server-Sent Events progress stream")
async def stream_job_progress(
    job_id: str,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    """
    SSE endpoint.  The client receives events as the worker progresses:
      - data: {"status":"running","current":1,"total":5}
      - data: {"status":"done","log_id":42}
      - data: {"status":"failed","error":"..."}
    """

    async def event_generator():
        last_current = -1
        poll_interval = 1.0  # seconds between Redis polls
        max_wait = 300        # 5 minutes max stream duration

        for _ in range(int(max_wait / poll_interval)):
            job = get_job(job_id)
            if job is None:
                yield _sse({"error": "job_not_found"})
                return

            status = job.get("status", "pending")
            current = job.get("current", 0)

            # Only push an event when something changed
            if current != last_current or status in ("done", "failed"):
                payload = {
                    "status": status,
                    "current": current,
                    "total": job.get("total", 0),
                    "log_id": job.get("log_id"),
                    "error": job.get("error"),
                }
                yield _sse(payload)
                last_current = current

            if status in ("done", "failed"):
                return

            await asyncio.sleep(poll_interval)

        yield _sse({"status": "timeout", "error": "Stream timeout after 5 minutes"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.get("/{job_id}/result", summary="Get full analysis result")
def get_job_result(
    job_id: str,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    """Returns the complete analysis payload once the job is done."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job not finished yet (status: {job['status']})",
        )
    return {"log_id": job.get("log_id"), "result": job.get("result")}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
