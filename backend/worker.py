"""
worker.py — Celery application + analysis task.
Start with:
    celery -A worker worker --loglevel=info --concurrency=2 -Q analysis
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from celery import Celery  # type: ignore

from core.job_store import update_job
from services.classifier import classify_error
from services.log_parser import parse_log_file
from services.ollama_service import analyze_with_ollama
from services import storage
from services.storage import get_cached_error_analysis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "log_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker (Ollama is slow)
    result_expires=7200,
)


def _run_async(coro):
    """Run an async coroutine in a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="worker.analyze_file_task", queue="analysis")
def analyze_file_task(
    self,
    job_id: str,
    file_content: str,
    filename: str,
    max_errors: int = 5,
    tenant_id: int | None = None,
    user_id: int | None = None,
):
    """
    Celery task: parse log content, call Ollama for each error (with RAG),
    store the result, and update job progress in Redis after each step.
    """
    update_job(job_id, status="running", current=0)

    try:
        entries = parse_log_file(file_content)
        total = min(len(entries), max_errors)
        update_job(job_id, total=total, status="running")

        if not entries:
            result_payload = {
                "filename": filename,
                "total_errors_found": 0,
                "total_analyzed": 0,
                "analyzed": [],
                "message": "Aucune erreur détectée dans ce fichier.",
            }
            log_id = storage.save_analysis(result_payload, tenant_id=tenant_id, user_id=user_id)
            update_job(job_id, status="done", result=result_payload, log_id=log_id, current=0)
            return result_payload

        to_analyze = entries[:max_errors]
        
        # Deduplicate error lines to avoid calling Ollama for duplicate errors
        unique_entries = {}
        occurrences = {}
        for entry in to_analyze:
            msg = entry.message
            occurrences[msg] = occurrences.get(msg, 0) + 1
            if msg not in unique_entries:
                unique_entries[msg] = entry

        total_unique = len(unique_entries)
        logger.info("Deduplicated %d entries into %d unique error signatures", total, total_unique)

        async def analyze_unique_entry(msg, entry):
            start = time.time()
            category = classify_error(entry.message)

            # 1. Check DB cache first — avoids Ollama for already-seen errors
            cached = get_cached_error_analysis(msg)
            if cached and cached.get("analysis", {}).get("explanation"):
                logger.info("Cache HIT for: %s...", msg[:60])
                return {
                    "message": msg,
                    "category": cached.get("category") or category,
                    "success": True,
                    "analysis": cached["analysis"],
                    "error": None,
                    "rag_used": False,
                    "from_cache": True,
                    "processing_time_seconds": round(time.time() - start, 3),
                }

            # 2. Not in cache — call Ollama (RAG disabled for batch perf: embed adds ~2s/error)
            logger.info("Cache MISS — calling Ollama for: %s...", msg[:60])
            log_line = f"{entry.timestamp} {entry.level} {entry.message}"
            result = await analyze_with_ollama(log_line, entry.level, use_rag=False)

            return {
                "message": msg,
                "category": category,
                "success": result["success"],
                "analysis": result["analysis"],
                "error": result["error"],
                "rag_used": result.get("rag_used", False),
                "from_cache": False,
                "processing_time_seconds": round(time.time() - start, 2),
            }

        async def run_parallel():
            # Keep this semaphore value equal to OLLAMA_NUM_PARALLEL in docker-compose.yml.
            # With OLLAMA_NUM_PARALLEL=1 and OLLAMA_MAX_LOADED_MODELS=1 (GTX 1650 Ti 4 GB),
            # a semaphore of 3 was creating GPU contention. Set to 2 to cap concurrent
            # Ollama calls to what the GPU can actually process in parallel.
            sem = asyncio.Semaphore(2)
            
            async def worker_task(msg, entry):
                async with sem:
                    return await analyze_unique_entry(msg, entry)

            tasks = [worker_task(msg, entry) for msg, entry in unique_entries.items()]
            unique_results = {}
            
            analyzed_count = 0
            # Run unique signatures concurrently (throttled by semaphore)
            for coro in asyncio.as_completed(tasks):
                res = await coro
                msg = res["message"]
                unique_results[msg] = res
                
                # Increment current by the number of times this error occurred in the file
                analyzed_count += occurrences[msg]
                update_job(job_id, current=min(analyzed_count, total))
                
            # Build the full results list matching the original log entries order
            results_list = []
            for idx, entry in enumerate(to_analyze):
                res = unique_results[entry.message]
                results_list.append({
                    "index": idx + 1,
                    "line_number": entry.line_number,
                    "timestamp": entry.timestamp,
                    "level": entry.level,
                    "message": entry.message,
                    "category": res["category"],
                    "success": res["success"],
                    "analysis": res["analysis"],
                    "error": res["error"],
                    "rag_used": res["rag_used"],
                    "from_cache": res.get("from_cache", False),
                    "processing_time_seconds": res["processing_time_seconds"],
                })
            return results_list

        results = _run_async(run_parallel())

        result_payload = {
            "filename": filename,
            "total_errors_found": len(entries),
            "total_analyzed": len(results),
            "skipped": max(0, len(entries) - max_errors),
            "analyzed": results,
        }

        try:
            log_id = storage.save_analysis(result_payload, tenant_id=tenant_id, user_id=user_id)
        except Exception:
            logger.exception("Failed to save analysis to DB")
            log_id = None

        # WhatsApp notification alert trigger for critical errors
        if len(entries) > 0:
            try:
                from services.whatsapp_service import send_whatsapp_notification
                error_levels = [entry.level for entry in entries]
                _run_async(send_whatsapp_notification(filename, len(entries), error_levels))
            except Exception:
                logger.exception("Failed to trigger WhatsApp notification")

        update_job(job_id, status="done", result=result_payload, log_id=log_id)
        return result_payload


    except Exception as exc:
        logger.exception("analyze_file_task failed", extra={"job_id": job_id})
        update_job(job_id, status="failed", error=str(exc))
        raise
