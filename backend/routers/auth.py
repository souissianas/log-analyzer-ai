import asyncio
import logging
import os
import hashlib
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends, Request
from core.jwt import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from core.security import get_current_user_or_api_key
import secrets
import time
from schemas.auth import UserRegister, UserLogin, Token, RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest
from services import storage
from services.whatsapp_service import send_whatsapp_message
from services.email_service import send_email

logger = logging.getLogger(__name__)

# ── Rate limiting ────────────────────────────────────────────────────────────
# Primary: Redis-backed sliding window (scales across replicas/pods).
# Fallback: in-memory dict (single-process only — used when Redis is offline).
_rate_limit_store: dict[str, list[float]] = {}
_rl_redis_client = None


def _get_rl_redis():
    """Return a Redis client for rate limiting, or None if unavailable."""
    global _rl_redis_client
    if _rl_redis_client is not None:
        return _rl_redis_client
    try:
        import redis as redis_lib  # type: ignore
        import os
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _rl_redis_client = redis_lib.from_url(url, decode_responses=True)
        _rl_redis_client.ping()
        return _rl_redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for rate limiting — using in-memory fallback: %s", exc)
        return None


def check_rate_limit(key: str, max_requests: int = 5, window_seconds: int = 900) -> bool:
    """Returns True if rate limit is exceeded, False otherwise.

    Uses a Redis sorted-set sliding window when Redis is available:
      - score = current timestamp
      - members outside the window are pruned on each call
      - TTL on the key prevents orphaned keys
    Falls back to in-memory dict (single-process) when Redis is offline.
    """
    now = time.time()
    r = _get_rl_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            rl_key = f"rl:{key}"
            # Remove timestamps older than the sliding window
            pipe.zremrangebyscore(rl_key, 0, now - window_seconds)
            # Count remaining attempts within the window
            pipe.zcard(rl_key)
            # Refresh TTL so idle keys expire automatically
            pipe.expire(rl_key, window_seconds + 1)
            _, count, _ = pipe.execute()
            return count >= max_requests
        except Exception as exc:
            logger.warning("Redis rate-limit check failed, falling back to memory: %s", exc)
            # Fall through to in-memory fallback below
    # In-memory fallback
    attempts = _rate_limit_store.get(key, [])
    attempts = [t for t in attempts if now - t < window_seconds]
    _rate_limit_store[key] = attempts
    return len(attempts) >= max_requests


def record_attempt(key: str):
    """Record one attempt for the given rate-limit key."""
    now = time.time()
    r = _get_rl_redis()
    if r is not None:
        try:
            rl_key = f"rl:{key}"
            # Use timestamp as both score and member (add small jitter to allow duplicates)
            pipe = r.pipeline()
            pipe.zadd(rl_key, {f"{now:.6f}": now})
            pipe.expire(rl_key, 901)  # window_seconds + 1 as safe TTL
            pipe.execute()
            return
        except Exception as exc:
            logger.warning("Redis record_attempt failed, falling back to memory: %s", exc)
    # In-memory fallback
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
    _rate_limit_store[key].append(now)


def hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Un utilisateur avec cet email existe déjà"},
        201: {"description": "Compte créé — token renvoyé si premier utilisateur (admin), sinon compte en attente de validation"},
    },
)
async def register(payload: UserRegister):
    # Check if user already exists
    existing_user = storage.get_user_by_email(payload.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email existe déjà"
        )
    # Check or create tenant
    tenant = storage.get_tenant_by_slug(payload.tenant_slug)
    if tenant:
        tenant_id = tenant["id"]
    else:
        tenant_id = storage.create_tenant(payload.tenant_name, payload.tenant_slug)
    # Determine status: first user in tenant becomes admin and is auto-activated
    existing_count = storage.count_users_by_tenant(tenant_id)
    is_first_user = existing_count == 0
    if is_first_user:
        user_role = "admin"
        user_status = "active"
    else:
        user_role = payload.role or "viewer"
        user_status = "pending"  # Must be validated by an admin
    # Create user
    hashed_pwd = get_password_hash(payload.password)
    user_id = storage.create_user(
        tenant_id=tenant_id,
        email=payload.email,
        role=user_role,
        hashed_password=hashed_pwd,
        status=user_status,
    )
    if not is_first_user:
        # Return info without a full access token — account is pending
        raise HTTPException(
            status_code=status.HTTP_201_CREATED,
            detail={
                "pending": True,
                "message": "Votre compte a été créé. Un administrateur doit valider votre accès avant que vous puissiez vous connecter.",
                "email": payload.email,
            }
        )
    # First user (admin) — create full JWT immediately
    token_data = {
        "sub": payload.email,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": user_role,
        "status": user_status,
    }
    token = create_access_token(token_data, expires_delta=timedelta(hours=8))
    refresh_token = create_refresh_token(token_data)
    return Token(
        access_token=token,
        refresh_token=refresh_token,
        role=user_role,
        email=payload.email,
    )


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"description": "Email ou mot de passe incorrect"},
        403: {"description": "Compte en attente de validation ou refusé"},
    },
)
async def login(payload: UserLogin):
    user = storage.get_user_by_email(payload.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    # Check account status
    user_status = user.get("status", "active")
    if user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte est en attente de validation par un administrateur.",
        )
    if user_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été refusé. Contactez un administrateur.",
        )
    token_data = {
        "sub": user["email"],
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "role": user["role"],
        "status": user_status,
    }
    token = create_access_token(token_data, expires_delta=timedelta(hours=8))
    refresh_token = create_refresh_token(token_data)
    return Token(
        access_token=token,
        refresh_token=refresh_token,
        role=user["role"],
        email=user["email"],
    )


@router.get(
    "/me",
    responses={
        404: {"description": "Utilisateur introuvable"},
    },
)
async def get_current_user_info(current_user: dict = Depends(get_current_user_or_api_key)):
    """Retourne les informations de l'utilisateur connecté."""
    user_id = current_user.get("user_id")
    if not user_id:
        return {
            "user_id": 0,
            "email": "system",
            "role": current_user.get("role", "admin"),
            "status": "active",
            "tenant_id": current_user.get("tenant_id"),
        }
    user = storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return {
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "status": user.get("status", "active"),
        "tenant_id": user["tenant_id"],
    }


@router.post(
    "/refresh",
    response_model=Token,
    responses={
        401: {"description": "Token de rafraîchissement invalide, expiré ou utilisateur introuvable"},
        403: {"description": "Compte en attente de validation ou refusé"},
    },
)
async def refresh(payload: RefreshRequest):
    # Decode refresh token
    token_data, error = decode_refresh_token(payload.refresh_token)
    if error is not None or not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraîchissement invalide ou expiré",
        )

    # Get user to verify status (status checked in DB, e.g. for revocation)
    user_id = token_data.get("user_id")
    user = storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    user_status = user.get("status", "active")
    if user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte est en attente de validation par un administrateur.",
        )
    if user_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été refusé. Contactez un administrateur.",
        )

    # Create new access and refresh tokens
    new_token_data = {
        "sub": user["email"],
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "role": user["role"],
        "status": user_status,
    }

    new_access_token = create_access_token(new_token_data, expires_delta=timedelta(hours=8))
    new_refresh_token = create_refresh_token(new_token_data)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        role=user["role"],
        email=user["email"],
    )


@router.post(
    "/forgot-password",
    responses={
        429: {"description": "Trop de demandes de réinitialisation (limite par IP ou par email atteinte)"},
    },
)
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    """Génère un OTP à 6 chiffres et l'envoie via WhatsApp si disponible."""
    email = body.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    # Rate limit by IP: max 10 requests per 15 minutes
    if check_rate_limit(f"ip_forgot_{client_ip}", max_requests=10, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de demandes de réinitialisation de mot de passe depuis cette adresse IP. Veuillez réessayer plus tard."
        )
    # Rate limit by Email: max 5 requests per 15 minutes
    if check_rate_limit(f"email_forgot_{email}", max_requests=5, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de demandes de réinitialisation de mot de passe pour cet e-mail. Veuillez réessayer plus tard."
        )
    record_attempt(f"ip_forgot_{client_ip}")
    record_attempt(f"email_forgot_{email}")
    user = storage.get_user_by_email(email)
    # Always return success to avoid email enumeration
    if not user:
        return {"message": "Si cet email existe, un code a été envoyé."}
    code = f"{secrets.randbelow(1_000_000):06d}"
    hashed_code = hash_otp(code)
    storage.save_otp(email, hashed_code, time.time() + 600)  # 10 min
    env = os.environ.get("ENV", "development")
    if env != "production":
        logger.info(f"[PASSWORD RESET] OTP pour {email}: {code}")
    else:
        logger.info(f"[PASSWORD RESET] OTP généré pour {email}")
    # Try to send via Email (SMTP)
    email_sent = False
    try:
        subject = "Réinitialisation de votre mot de passe - Log Analyzer AI"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e1e1e1; border-radius: 8px;">
                    <h2 style="color: #4f46e5;">Log Analyzer AI</h2>
                    <p>Bonjour,</p>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe. Voici votre code de vérification à 6 chiffres :</p>
                    <div style="font-size: 24px; font-weight: bold; letter-spacing: 4px; text-align: center; margin: 30px 0; padding: 15px; background-color: #f3f4f6; border-radius: 6px; color: #1e1b4b;">
                        {code}
                    </div>
                    <p>Ce code est valable pendant 10 minutes. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail en toute sécurité.</p>
                    <hr style="border: 0; border-top: 1px solid #e1e1e1; margin: 20px 0;" />
                    <p style="font-size: 12px; color: #6b7280;">Ce message a été envoyé automatiquement, merci de ne pas y répondre.</p>
                </div>
            </body>
        </html>
        """
        email_sent = await send_email(email, subject, html_body)
        if email_sent:
            logger.info(f"[PASSWORD RESET] Email envoyé à {email}")
    except Exception as exc:
        logger.warning(f"[PASSWORD RESET] Erreur d'envoi d'email SMTP: {exc}")
    # Try to send via WhatsApp
    whatsapp_sent = False
    try:
        whatsapp_sent = await send_whatsapp_message(
            f"Votre code de réinitialisation Log Analyzer AI est : {code}\n"
            f"Il expire dans 10 minutes."
        )
        if whatsapp_sent:
            logger.info(f"[PASSWORD RESET] WhatsApp envoyé à {email}")
    except Exception as exc:
        logger.warning(f"[PASSWORD RESET] Erreur WhatsApp: {exc}")
    if not email_sent and not whatsapp_sent:
        logger.warning("[PASSWORD RESET] Aucun canal (Email/WhatsApp) disponible, code visible uniquement dans les logs.")
    return {"message": "Si cet email existe, un code a été envoyé."}


@router.post(
    "/reset-password",
    responses={
        400: {"description": "Aucun code actif, code expiré ou code incorrect"},
        429: {"description": "Trop de tentatives de réinitialisation (limite par IP ou par email atteinte)"},
    },
)
async def reset_password(body: ResetPasswordRequest, request: Request):
    """Vérifie l'OTP et met à jour le mot de passe."""
    email = body.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    # Rate limit by IP: max 10 attempts per 15 minutes
    if check_rate_limit(f"ip_reset_{client_ip}", max_requests=10, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de réinitialisation de mot de passe depuis cette adresse IP. Veuillez réessayer plus tard."
        )
    # Rate limit by Email: max 5 attempts per 15 minutes
    if check_rate_limit(f"email_reset_{email}", max_requests=5, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de validation de code pour cet e-mail. Veuillez réessayer plus tard."
        )
    record_attempt(f"ip_reset_{client_ip}")
    record_attempt(f"email_reset_{email}")
    entry = storage.get_otp(email)
    if not entry:
        raise HTTPException(status_code=400, detail="Aucun code de réinitialisation actif pour cet email.")
    if time.time() > entry["expires"]:
        storage.delete_otp(email)
        raise HTTPException(status_code=400, detail="Le code a expiré. Veuillez en demander un nouveau.")
    if entry["code"] != hash_otp(body.code):
        raise HTTPException(status_code=400, detail="Code incorrect.")
    hashed = get_password_hash(body.new_password)
    storage.update_user_password(email, hashed)
    storage.delete_otp(email)
    logger.info(f"[PASSWORD RESET] Mot de passe mis à jour pour {email}")
    return {"message": "Mot de passe mis à jour avec succès."}
