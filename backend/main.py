# backend/main.py

import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.metrics import HTTP_REQUESTS, metrics_payload
from services import storage

from routers.auth import router as auth_router
from routers.logs import router as logs_router, stats_router
from routers.jobs import router as jobs_router
from routers.health import router as health_router
from routers.ollama import router as ollama_router
from routers.admin import router as admin_router
from routers.analyze import router as analyze_router
from routers.users import router as users_router

from core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Log Analyzer AI", version="2.0.0")

# Background tasks created with asyncio.create_task() are only weakly
# referenced by the event loop — if nothing else holds a reference, the
# task can be garbage-collected mid-execution and silently cancelled.
# Keeping a strong reference here (removed via the done-callback once the
# task finishes) is the pattern recommended by the asyncio docs.
_background_tasks: set = set()

@app.on_event("startup")
async def startup_event():
    # Initialise la base de données SQLite locale
    storage.init_db()
    logger.info("Storage DB initialisée")

    # Pré-chauffe Ollama : charge le modèle en RAM au démarrage du backend
    # plutôt que d'attendre la première analyse utilisateur. Sans ça, le
    # tout premier appel à /ollama/analyze-file ou /jobs/analyze paie le
    # coût de chargement du modèle (plusieurs secondes) en plus du temps
    # de génération, ce qui donne l'impression que "le premier fichier
    # analysé est très lent". Non-bloquant : le backend démarre même si
    # Ollama n'est pas encore disponible.
    import asyncio

    async def _warm_up_ollama():
        try:
            from services.ollama_service import (
                OLLAMA_BASE_URL,
                OLLAMA_MODEL,
                OLLAMA_KEEP_ALIVE,
            )
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": "ping",
                        "stream": False,
                        "keep_alive": OLLAMA_KEEP_ALIVE,
                        "options": {"num_predict": 1},
                    },
                )
            logger.info("Ollama pre-warmed: model %s loaded into RAM", OLLAMA_MODEL)
        except Exception as exc:
            logger.warning("Ollama pre-warm skipped (Ollama likely not running yet): %s", exc)

    warm_up_task = asyncio.create_task(_warm_up_ollama())
    _background_tasks.add(warm_up_task)
    warm_up_task.add_done_callback(_background_tasks.discard)

# Prometheus Metrics Middleware
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    path = request.url.path
    response = await call_next(request)
    if path not in ("/metrics", "/health"):
        HTTP_REQUESTS.labels(
            method=request.method,
            path=path,
            status=str(response.status_code)
        ).inc()
    return response

@app.get("/metrics")
def get_metrics():
    return Response(content=metrics_payload(), media_type="text/plain")

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(ollama_router)
app.include_router(logs_router)
app.include_router(stats_router)
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(analyze_router)
app.include_router(users_router)
