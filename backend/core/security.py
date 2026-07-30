"""
core/security.py
Authentication dependencies — JWT Bearer + API Key.

Corrections appliquées :
  1. Court-circuit auth_enabled=False  → plus de 401 en mode dev
  2. hmac.compare_digest()             → protection timing attack sur l'API Key
  3. Avertissement api_key_query       → commentaire sécurité en prod
  4. Suppression des `async` inutiles  → aucune de ces fonctions n'utilise `await`
     (code smell SonarQube : "Use asynchronous features in this function
     or remove the async keyword")
"""
import hmac
import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings
from core.jwt import decode_token, decode_token_full

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)


def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key: Optional[str] = Security(api_key_header),
    # NOTE sécurité : la clé en query string apparaît dans les logs Nginx/serveur
    # et dans l'historique navigateur. Acceptable en démo, déconseillé en production.
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> dict:
    settings = get_settings()

    # ── 1. Vérification JWT Bearer ─────────────────────────────────────────
    if credentials:
        token = credentials.credentials
        payload, error = decode_token_full(token)
        if payload is not None:
            logger.info(
                "JWT authentication successful",
                extra={"event": "auth_jwt_ok", "sub": payload.get("sub")},
            )
            return payload
        elif error == "expired":
            logger.warning("Expired JWT token presented", extra={"event": "auth_jwt_expired"})
            raise HTTPException(
                status_code=401,
                detail="Token JWT expiré",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            logger.warning("Invalid JWT token presented", extra={"event": "auth_jwt_invalid"})
            raise HTTPException(
                status_code=401,
                detail="Token JWT invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # ── 2. Vérification API Key ────────────────────────────────────────────
    provided_api_key = api_key or api_key_query
    if provided_api_key and settings.api_key:
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

    # ── 3. Court-circuit si l'auth est désactivée (mode dev sans clé API ni token) ─
    if not settings.auth_enabled:
        return {
            "sub": "anonymous",
            "user_id": None,
            "tenant_id": None,
            "role": "admin",
        }

    raise HTTPException(
        status_code=401,
        detail="Authentification requise : token JWT ou clé API invalide ou manquante",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_key(
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
    def dependency(
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
