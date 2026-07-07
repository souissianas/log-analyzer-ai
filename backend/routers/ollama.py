import asyncio
import logging
import time

from fastapi import APIRouter, Depends, File, UploadFile

from core.metrics import LOG_ANALYSIS_TOTAL, LOG_ERRORS_DETECTED, OLLAMA_REQUEST_DURATION
from core.security import get_current_user_or_api_key
from core.upload import decode_upload, read_upload_with_limit, validate_log_extension
from schemas.analysis import AnalysisResultResponse, AnalyzedErrorItem
from services.classifier import classify_error
from services.log_parser import parse_log_file
from services.ollama_service import analyze_with_ollama
from services import storage
from services.storage import get_cached_error_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama", tags=["ollama"])


@router.post("/analyze-line")
async def analyze_single_line(
    log_line: str,
    error_level: str = "ERROR",
    output_format: str = "structured",
    current_user: dict = Depends(get_current_user_or_api_key),
):
    from fastapi import HTTPException

    role = current_user.get("role", "viewer")
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Rôle insuffisant : viewer ne peut pas analyser.")

    if not log_line.strip():
        raise HTTPException(status_code=400, detail="La ligne de log est vide")

    start = time.time()
    result = await analyze_with_ollama(log_line, error_level, output_format=output_format)
    OLLAMA_REQUEST_DURATION.observe(time.time() - start)

    return {
        "success": result["success"],
        "log_line": log_line,
        "error_level": error_level,
        "category": classify_error(log_line),
        "analysis": result["analysis"],
        "raw_response": result["raw_response"],
        "error": result["error"],
        "processing_time_seconds": round(time.time() - start, 2),
    }


@router.post("/analyze-file", response_model=AnalysisResultResponse)
async def analyze_file_with_ai(
    file: UploadFile = File(...),
    max_errors: int = 5,
    output_format: str = "structured",
    current_user: dict = Depends(get_current_user_or_api_key),
):
    from fastapi import HTTPException

    role = current_user.get("role", "viewer")
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Rôle insuffisant : viewer ne peut pas analyser.")

    validate_log_extension(file.filename)

    content_bytes = await read_upload_with_limit(file)
    content = decode_upload(content_bytes)
    entries = parse_log_file(content)

    if not entries:
        return AnalysisResultResponse(
            filename=file.filename,
            total_errors_found=0,
            total_analyzed=0,
            analyzed=[],
            message="Aucune erreur détectée dans ce fichier.",
        )

    to_analyze = entries[:max_errors]
    logger.info("%s : %s erreurs, analyse de %s", file.filename, len(entries), len(to_analyze))

    # Perf : mêmes optimisations que le flux asynchrone (worker.py) —
    # dédup des messages identiques, cache DB, et parallélisme borné.
    # Avant : une boucle séquentielle "await" par erreur, ce qui pouvait
    # prendre 30s+ même pour un petit fichier avec seulement quelques
    # erreurs (chaque appel Ollama coûte plusieurs secondes).
    unique_entries: dict[str, object] = {}
    for entry in to_analyze:
        if entry.message not in unique_entries:
            unique_entries[entry.message] = entry

    sem = asyncio.Semaphore(3)  # 3 appels Ollama concurrents max

    async def analyze_unique(message: str, entry) -> dict:
        start = time.time()
        category = classify_error(entry.message)

        cached = get_cached_error_analysis(message)
        if cached and cached.get("analysis", {}).get("explanation"):
            return {
                "message": message,
                "category": cached.get("category") or category,
                "success": True,
                "analysis": cached["analysis"],
                "error": None,
                "processing_time_seconds": round(time.time() - start, 3),
            }

        async with sem:
            log_line = f"{entry.timestamp} {entry.level} {entry.message}"
            # RAG désactivé par défaut ici pour la rapidité (chaque recherche
            # RAG ajoute un aller-retour d'embedding, ~1-2s de plus par erreur).
            result = await analyze_with_ollama(log_line, entry.level, output_format=output_format, use_rag=False)
            OLLAMA_REQUEST_DURATION.observe(time.time() - start)

        return {
            "message": message,
            "category": category,
            "success": result["success"],
            "analysis": result["analysis"],
            "error": result["error"],
            "processing_time_seconds": round(time.time() - start, 2),
        }

    unique_results = {}
    tasks = [analyze_unique(msg, entry) for msg, entry in unique_entries.items()]
    for coro in asyncio.as_completed(tasks):
        res = await coro
        unique_results[res["message"]] = res

    results: list[AnalyzedErrorItem] = []
    for index, entry in enumerate(to_analyze):
        res = unique_results[entry.message]
        results.append(
            AnalyzedErrorItem(
                index=index + 1,
                line_number=entry.line_number,
                timestamp=entry.timestamp,
                level=entry.level,
                message=entry.message,
                category=res["category"],
                success=res["success"],
                analysis=res["analysis"],
                error=res["error"],
                processing_time_seconds=res["processing_time_seconds"],
            )
        )

    tenant_id = current_user.get("tenant_id")
    user_id = current_user.get("user_id")

    result_payload = {
        "filename": file.filename,
        "total_errors_found": len(entries),
        "total_analyzed": len(results),
        "skipped": max(0, len(entries) - max_errors),
        "analyzed": [item.model_dump() for item in results],
    }

    try:
        log_id = storage.save_analysis(result_payload, tenant_id=tenant_id, user_id=user_id)
        LOG_ANALYSIS_TOTAL.inc()
        LOG_ERRORS_DETECTED.inc(len(entries))
    except Exception:
        logger.exception("Erreur lors de la sauvegarde de l'analyse")
        log_id = None

    return AnalysisResultResponse(log_id=log_id, **result_payload)