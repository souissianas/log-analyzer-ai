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


# ── Helpers extraits pour réduire la complexité cognitive ─────────────────────

def _empty_result_payload(filename: str) -> dict:
    """Payload renvoyé quand aucune erreur n'a été détectée dans le fichier."""
    return {
        "filename": filename,
        "total_errors_found": 0,
        "total_analyzed": 0,
        "analyzed": [],
        "message": "Aucune erreur détectée dans ce fichier.",
    }


def _deduplicate_entries(to_analyze: list) -> tuple[dict, dict]:
    """Regroupe les entrées par message unique et compte leurs occurrences."""
    unique_entries: dict = {}
    occurrences: dict = {}
    for entry in to_analyze:
        msg = entry.message
        occurrences[msg] = occurrences.get(msg, 0) + 1
        if msg not in unique_entries:
            unique_entries[msg] = entry
    return unique_entries, occurrences


def _cached_analysis_result(msg: str, category: str, start: float) -> dict | None:
    """Retourne un résultat basé sur le cache DB, ou None si pas de cache exploitable."""
    cached = get_cached_error_analysis(msg)
    if not cached or not cached.get("analysis", {}).get("explanation"):
        return None

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


async def _analyze_unique_entry(msg: str, entry) -> dict:
    """Analyse un signature d'erreur unique : cache DB, sinon appel Ollama."""
    start = time.time()
    category = classify_error(entry.message)

    cached_result = _cached_analysis_result(msg, category, start)
    if cached_result is not None:
        return cached_result

    # Pas en cache — appel Ollama (RAG désactivé pour perf batch : embed ajoute ~2s/erreur)
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


async def _run_unique_analyses(job_id: str, unique_entries: dict, occurrences: dict, total: int) -> dict:
    """Lance les analyses uniques en parallèle (throttlées) et met à jour la progression."""
    # Garder cette valeur de sémaphore égale à OLLAMA_NUM_PARALLEL dans docker-compose.yml.
    # Avec OLLAMA_NUM_PARALLEL=1 et OLLAMA_MAX_LOADED_MODELS=1 (GTX 1650 Ti 4 GB),
    # un sémaphore de 3 créait de la contention GPU. Mis à 2 pour plafonner les appels
    # Ollama concurrents à ce que le GPU peut réellement traiter en parallèle.
    sem = asyncio.Semaphore(2)

    async def worker_task(msg, entry):
        async with sem:
            return await _analyze_unique_entry(msg, entry)

    tasks = [worker_task(msg, entry) for msg, entry in unique_entries.items()]
    unique_results: dict = {}
    analyzed_count = 0

    for coro in asyncio.as_completed(tasks):
        res = await coro
        msg = res["message"]
        unique_results[msg] = res
        analyzed_count += occurrences[msg]
        update_job(job_id, current=min(analyzed_count, total))

    return unique_results


def _build_results_list(to_analyze: list, unique_results: dict) -> list:
    """Reconstruit la liste complète des résultats dans l'ordre original du log."""
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


async def _analyze_entries(job_id: str, to_analyze: list, total: int) -> list:
    """Déduplique, analyse en parallèle, puis reconstruit la liste ordonnée des résultats."""
    unique_entries, occurrences = _deduplicate_entries(to_analyze)
    logger.info(
        "Deduplicated %d entries into %d unique error signatures",
        total, len(unique_entries),
    )
    unique_results = await _run_unique_analyses(job_id, unique_entries, occurrences, total)
    return _build_results_list(to_analyze, unique_results)


def _save_analysis_safe(result_payload: dict, tenant_id, user_id):
    """Sauvegarde l'analyse en DB ; ne propage jamais l'exception (best-effort)."""
    try:
        return storage.save_analysis(result_payload, tenant_id=tenant_id, user_id=user_id)
    except Exception:
        logger.exception("Failed to save analysis to DB")
        return None



# ── Task Celery ────────────────────────────────────────────────────────────────

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
            result_payload = _empty_result_payload(filename)
            log_id = storage.save_analysis(result_payload, tenant_id=tenant_id, user_id=user_id)
            update_job(job_id, status="done", result=result_payload, log_id=log_id, current=0)
            return result_payload

        to_analyze = entries[:max_errors]
        results = _run_async(_analyze_entries(job_id, to_analyze, total))

        result_payload = {
            "filename": filename,
            "total_errors_found": len(entries),
            "total_analyzed": len(results),
            "skipped": max(0, len(entries) - max_errors),
            "analyzed": results,
        }

        log_id = _save_analysis_safe(result_payload, tenant_id, user_id)

        update_job(job_id, status="done", result=result_payload, log_id=log_id)
        return result_payload

    except Exception as exc:
        logger.exception("analyze_file_task failed", extra={"job_id": job_id})
        update_job(job_id, status="failed", error=str(exc))
        raise
