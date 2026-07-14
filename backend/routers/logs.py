import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.security import get_current_user_or_api_key
from schemas.analysis import AnalysisDetailResponse, AnalysisListResponse, AnalysisListItem
from services import storage
from services.ollama_service import analyze_with_ollama
from services.classifier import classify_error
from services.pdf_export import build_analysis_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["logs"])
stats_router = APIRouter(prefix="/stats", tags=["stats"])

ANALYSE_NOT_FOUND = "Analyse introuvable"


@stats_router.get("/dashboard")
def get_dashboard_stats(
    current_user: dict = Depends(get_current_user_or_api_key),
):
    """Retourne les statistiques globales pour le dashboard."""
    tenant_id = current_user.get("tenant_id")
    return storage.get_dashboard_stats(tenant_id=tenant_id)


@router.get("", response_model=AnalysisListResponse)
def list_saved_analyses(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    tenant_id = current_user.get("tenant_id")
    items = storage.list_analyses(limit=limit, offset=offset, tenant_id=tenant_id)
    total_count = storage.count_analyses(tenant_id=tenant_id)
    return AnalysisListResponse(
        count=total_count,
        items=[AnalysisListItem(**item) for item in items],
    )


@router.get(
    "/{log_id}",
    response_model=AnalysisDetailResponse,
    responses={
        404: {"description": ANALYSE_NOT_FOUND},
    },
)
def get_saved_analysis(
    log_id: int,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    tenant_id = current_user.get("tenant_id")
    item = storage.get_analysis(log_id, tenant_id=tenant_id)
    if not item:
        raise HTTPException(status_code=404, detail=ANALYSE_NOT_FOUND)
    return AnalysisDetailResponse(**item)


@router.post(
    "/{log_id}/export",
    responses={
        403: {"description": "Droit insuffisant pour exporter les analyses"},
        404: {"description": ANALYSE_NOT_FOUND},
    },
)
def export_analysis_pdf(
    log_id: int,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Droit insuffisant pour exporter les analyses")

    tenant_id = current_user.get("tenant_id")
    item = storage.get_analysis(log_id, tenant_id=tenant_id)
    if not item:
        raise HTTPException(status_code=404, detail=ANALYSE_NOT_FOUND)

    bio = build_analysis_pdf(item)
    return StreamingResponse(
        bio,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="analysis_{log_id}.pdf"'},
    )


@router.post(
    "/{log_id}/reanalyze",
    responses={
        403: {"description": "Droit insuffisant pour relancer l'analyse"},
        404: {"description": ANALYSE_NOT_FOUND},
    },
)
async def reanalyze_saved(
    log_id: int,
    max_errors: int = 5,
    current_user: dict = Depends(get_current_user_or_api_key),
):
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Droit insuffisant pour relancer l'analyse")
    tenant_id = current_user.get("tenant_id")
    user_id = current_user.get("user_id")
    item = storage.get_analysis(log_id, tenant_id=tenant_id)
    if not item:
        raise HTTPException(status_code=404, detail=ANALYSE_NOT_FOUND)

    old = item.get("data") or {}
    analyzed = old.get("analyzed", [])[:max_errors]
    results = []
    for index, entry in enumerate(analyzed):
        log_line = (
            f"{entry.get('timestamp', '')} {entry.get('level', '')} {entry.get('message', '')}"
        )
        response = await analyze_with_ollama(log_line, entry.get("level", "ERROR"))
        results.append(
            {
                "index": index + 1,
                "line_number": entry.get("line_number"),
                "timestamp": entry.get("timestamp"),
                "level": entry.get("level"),
                "message": entry.get("message"),
                "category": classify_error(entry.get("message", "")),
                "success": response.get("success"),
                "analysis": response.get("analysis"),
                "error": response.get("error"),
            }
        )
    new_payload = {
        "filename": old.get("filename", f"reanalyze_{log_id}"),
        "total_errors_found": len(old.get("analyzed", [])),
        "total_analyzed": len(results),
        "skipped": max(0, len(old.get("analyzed", [])) - max_errors),
        "analyzed": results,
    }
    new_id = storage.save_analysis(new_payload, tenant_id=tenant_id, user_id=user_id)
    return {"new_log_id": new_id, "result": new_payload}
