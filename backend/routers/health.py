from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.config import get_settings
from schemas.health import HealthResponse, ReadinessResponse
from services import storage
from services.ollama_service import check_ollama_health

router = APIRouter(tags=["health"])


@router.get("/", response_model=dict)
def root():
    settings = get_settings()
    return {"message": "Log Analyzer AI is running", "version": settings.app_version}


@router.get("/health", response_model=HealthResponse)
def health_check():
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        503: {"description": "Service dégradé — base de données ou Ollama indisponible"},
    },
)
async def readiness_check():
    db = storage.check_db_health()
    ollama = await check_ollama_health()
    ready = db["ok"] and ollama["ollama_running"] and ollama["model_available"]
    payload = ReadinessResponse(
        status="ready" if ready else "degraded",
        database=db,
        ollama=ollama,
    )
    if not ready:
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload


@router.get(
    "/ollama/health",
    responses={
        503: {"description": "Ollama non disponible ou modèle requis introuvable"},
    },
)
async def ollama_health():
    health = await check_ollama_health()
    if not health["ollama_running"]:
        raise HTTPException(status_code=503, detail="Ollama non disponible. Lance : ollama serve")
    if not health["model_available"]:
        raise HTTPException(
            status_code=503,
            detail=f"Modèle '{health['required_model']}' introuvable. Lance : ollama pull llama3.2",
        )
    return health
