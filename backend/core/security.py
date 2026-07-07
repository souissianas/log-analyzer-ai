"""
core/security.py
Authentication dependencies — JWT Bearer + API Key.

Corrections appliquées :
  1. Court-circuit auth_enabled=False  → plus de 401 en mode dev
  2. hmac.compare_digest()             → protection timing attack sur l'API Key
  3. Avertissement api_key_query       → commentaire sécurité en prod
"""
import hmac
import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings
from core.jwt import decode_token

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key: Optional[str] = Security(api_key_header),
    # NOTE sécurité : la clé en query string apparaît dans les logs Nginx/serveur
    # et dans l'historique navigateur. Acceptable en démo, déconseillé en production.
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> dict:
    settings = get_settings()

    # ── FIX 1 : court-circuit si l'auth est désactivée ────────────────────
    # Sans ça, le code tombait toujours sur le 401 final quand auth_enabled=False
    # car ni le bloc API Key ni le bloc JWT ne passaient.
    if not settings.auth_enabled:
        return {
            "sub": "anonymous",
            "user_id": None,
            "tenant_id": None,
            "role": "admin",
        }

    # ── 1. Vérification API Key ────────────────────────────────────────────
    provided_api_key = api_key or api_key_query
    if provided_api_key and settings.api_key:
        # FIX 2 : compare_digest() empêche les timing attacks
        # (comparaison en temps constant, indépendant de la longueur commune)
        if hmac.compare_digest(provided_api_key, settings.api_key):
            logger.info(
                "API key authentication successful",
                extra={"event": "auth_api_key_ok"},
            )
            return {
                "sub": "system-api-key",
                "user_id": None,
                "tenant_id": None,
                "role": "admin",
            }
        else:
            logger.warning(
                "Invalid API key provided",
                extra={"event": "auth_api_key_fail"},
            )

    # ── 2. Vérification JWT Bearer ─────────────────────────────────────────
    if credentials:
        token = credentials.credentials
        payload = decode_token(token)
        if payload is not None:
            logger.info(
                "JWT authentication successful",
                extra={"event": "auth_jwt_ok", "sub": payload.get("sub")},
            )
            return payload
        else:
            logger.warning(
                "Invalid or expired JWT token",
                extra={"event": "auth_jwt_fail"},
            )

    raise HTTPException(
        status_code=401,
        detail="Authentification requise : token JWT ou clé API invalide ou manquante",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_api_key(
    api_key: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> Optional[str]:
    """Compatibilité legacy — utilisé par les anciens endpoints."""
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    provided = api_key or api_key_query
    if not provided or not settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    # FIX 2 : compare_digest ici aussi
    if not hmac.compare_digest(provided, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return provided


def require_role(allowed_roles: List[str]):
    """
    Dépendance FastAPI pour le contrôle d'accès par rôle (RBAC).

    Usage :
        @router.get("/admin/users")
        async def list_users(user=Depends(require_role(["admin"]))):
            ...
    """
    async def dependency(
        current_user: dict = Depends(get_current_user_or_api_key),
    ) -> dict:
        role = current_user.get("role")
        if role not in allowed_roles:
            logger.warning(
                "Access denied — insufficient role",
                extra={
                    "event": "auth_role_denied",
                    "required": allowed_roles,
                    "actual": role,
                    "sub": current_user.get("sub"),
                },
            )
            raise HTTPException(
                status_code=403,
                detail=f"Droit insuffisant. Rôles requis : {', '.join(allowed_roles)}",
            )
        return current_user

    return dependency