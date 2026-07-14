import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.security import require_role
from services import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# --- Messages d'erreur centralisés (évite la duplication détectée par SonarCloud) ---
USER_NOT_FOUND = "Utilisateur introuvable"
TENANT_ACCESS_DENIED = "Accès refusé : utilisateur hors de votre organisation."


class StatusUpdate(BaseModel):
    status: str  # pending | active | rejected


class RoleUpdate(BaseModel):
    role: str  # admin | analyst | viewer


@router.get("")
async def list_users(current_user: dict = Depends(require_role(["admin"]))):
    """Liste tous les utilisateurs du tenant de l'admin connecté."""
    tenant_id = current_user.get("tenant_id")
    users = storage.list_users(tenant_id=tenant_id)
    # Don't expose hashed_password
    return [
        {
            "id": u["id"],
            "email": u["email"],
            "role": u["role"],
            "status": u.get("status", "active"),
            "tenant_id": u["tenant_id"],
            "created_at": u.get("created_at"),
        }
        for u in users
    ]


@router.patch(
    "/{user_id}/status",
    responses={
        400: {"description": "Statut invalide ou mise à jour impossible, ou tentative de modification de son propre statut."},
        403: {"description": "Utilisateur hors du tenant de l'admin connecté."},
        404: {"description": "Utilisateur introuvable."},
    },
)
async def update_user_status(
    user_id: int,
    payload: StatusUpdate,
    current_user: dict = Depends(require_role(["admin"])),
):
    """Active ou rejette un compte utilisateur."""
    if payload.status not in ("pending", "active", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Statut invalide. Valeurs acceptées : pending, active, rejected",
        )

    # Prevent admin from deactivating themselves
    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre statut.")

    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    # Tenant isolation: admin can only manage users in their own tenant
    if target_user.get("tenant_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail=TENANT_ACCESS_DENIED)

    success = storage.update_user_status(user_id, payload.status)
    if not success:
        raise HTTPException(status_code=400, detail="Mise à jour du statut échouée.")

    return {"success": True, "user_id": user_id, "status": payload.status}


@router.patch(
    "/{user_id}/role",
    responses={
        400: {"description": "Rôle invalide ou mise à jour impossible, ou tentative de modification de son propre rôle."},
        403: {"description": "Utilisateur hors du tenant de l'admin connecté."},
        404: {"description": "Utilisateur introuvable."},
    },
)
async def update_user_role(
    user_id: int,
    payload: RoleUpdate,
    current_user: dict = Depends(require_role(["admin"])),
):
    """Modifie le rôle d'un utilisateur."""
    if payload.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(
            status_code=400,
            detail="Rôle invalide. Valeurs acceptées : admin, analyst, viewer",
        )

    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre rôle.")

    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    if target_user.get("tenant_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail=TENANT_ACCESS_DENIED)

    success = storage.update_user_role(user_id, payload.role)
    if not success:
        raise HTTPException(status_code=400, detail="Mise à jour du rôle échouée.")

    return {"success": True, "user_id": user_id, "role": payload.role}


@router.delete(
    "/{user_id}",
    responses={
        400: {"description": "Tentative de suppression de son propre compte."},
        403: {"description": "Utilisateur hors du tenant de l'admin connecté."},
        404: {"description": "Utilisateur introuvable."},
    },
)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(require_role(["admin"])),
):
    """Supprime un utilisateur du tenant."""
    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte.")

    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    if target_user.get("tenant_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail=TENANT_ACCESS_DENIED)

    storage.delete_user(user_id)
    return {"success": True, "user_id": user_id, "deleted": True}
