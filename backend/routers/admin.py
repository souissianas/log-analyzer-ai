import logging

from fastapi import APIRouter, Depends, HTTPException

from core.security import require_api_key
from services import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/db", tags=["admin"], dependencies=[Depends(require_api_key)])


@router.post(
    "/migrate",
    responses={
        400: {"description": "DATABASE_URL non défini — PostgreSQL n'est pas configuré."},
        500: {"description": "psycopg2 manquant sur le serveur, ou échec de la migration."},
    },
)
def migrate_database(overwrite: bool = False):
    if not storage.DATABASE_URL:
        raise HTTPException(
            status_code=400,
            detail="DATABASE_URL non défini. PostgreSQL n'est pas configuré.",
        )
    if not getattr(storage, "psycopg2", None):
        raise HTTPException(status_code=500, detail="psycopg2 n'est pas installé sur le serveur.")

    try:
        result = storage.migrate_sqlite_to_postgres(overwrite=overwrite)
        return {"success": True, "migration": result}
    except Exception as exc:
        logger.exception("Migration PostgreSQL échouée")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
