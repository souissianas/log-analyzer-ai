"""
core/jwt.py
Gestion des tokens JWT et hashage des mots de passe.

Corrections appliquées :
  1. Import bcrypt déplacé dans le bloc fallback → plus de crash au démarrage
     si bcrypt n'est pas installé et que passlib est absent aussi.
  2. decode_token() distingue maintenant token expiré vs token invalide
     pour permettre au frontend de proposer un refresh intelligemment.
  3. create_refresh_token() ajouté pour compléter le flow auth.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional, Tuple

from jose import ExpiredSignatureError, JWTError, jwt

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── Hashage mot de passe : passlib en priorité, bcrypt direct en fallback ──
# On importe toujours bcrypt directement comme fallback de sécurité,
# car passlib peut échouer à la vérification si sa version est incompatible
# avec la version de bcrypt installée (AttributeError sur __about__).
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _USE_PASSLIB = True
except Exception:
    _pwd_context = None
    _USE_PASSLIB = False

# Toujours importer bcrypt directement comme fallback fiable
try:
    import bcrypt as _bcrypt_lib
except ImportError:
    _bcrypt_lib = None
    logger.error(
        "Ni passlib ni bcrypt ne sont disponibles — le hashage de mots de passe est désactivé",
        extra={"event": "bcrypt_unavailable"},
    )


# ── Hashage ────────────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash bcrypt.
    
    Stratégie : bcrypt direct en priorité (plus fiable avec les nouvelles
    versions de bcrypt), passlib en fallback si bcrypt n'est pas disponible.
    """
    # 1. Toujours essayer bcrypt direct en premier (évite le bug passlib/__about__)
    if _bcrypt_lib is not None:
        try:
            hashed_bytes = (
                hashed_password.encode("utf-8")
                if isinstance(hashed_password, str)
                else hashed_password
            )
            return _bcrypt_lib.checkpw(plain_password.encode("utf-8"), hashed_bytes)
        except Exception as exc:
            logger.warning("bcrypt direct verify failed, trying passlib fallback", extra={"error": str(exc)})

    # 2. Fallback passlib
    if _USE_PASSLIB and _pwd_context:
        try:
            return _pwd_context.verify(plain_password, hashed_password)
        except Exception as exc:
            logger.error("passlib verify failed", extra={"error": str(exc)})

    return False


def get_password_hash(password: str) -> str:
    """Hache un mot de passe avec bcrypt.
    
    Stratégie : bcrypt direct en priorité pour cohérence avec verify_password.
    """
    # 1. bcrypt direct en priorité
    if _bcrypt_lib is not None:
        try:
            return _bcrypt_lib.hashpw(
                password.encode("utf-8"), _bcrypt_lib.gensalt()
            ).decode("utf-8")
        except Exception as exc:
            logger.warning("bcrypt direct hash failed, trying passlib fallback", extra={"error": str(exc)})

    # 2. Fallback passlib
    if _USE_PASSLIB and _pwd_context:
        try:
            return _pwd_context.hash(password)
        except Exception as exc:
            logger.error("passlib hash failed", extra={"error": str(exc)})

    raise RuntimeError("Aucune bibliothèque bcrypt disponible pour hasher le mot de passe")


# ── Création de tokens ─────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un access token JWT (durée de vie courte : 60 min par défaut)."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crée un refresh token JWT (durée de vie longue : 7 jours par défaut).
    Le frontend peut l'utiliser pour obtenir un nouvel access token sans re-login.
    """
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ── Décodage de tokens ─────────────────────────────────────────────────────

# FIX 2 : decode_token retourne maintenant un tuple (payload, error_type)
# pour distinguer token expiré (→ proposer refresh) vs token invalide (→ re-login forcé).
# L'ancienne signature `-> Optional[dict]` est conservée via l'alias decode_token_simple.

DecodeError = Literal["expired", "invalid", None]


def decode_token_full(token: str) -> Tuple[Optional[Dict[str, Any]], DecodeError]:
    """
    Décode un token JWT et retourne (payload, error_type).

    Retours possibles :
        (payload_dict, None)      → token valide
        (None, "expired")         → token signé mais expiré → proposer un refresh
        (None, "invalid")         → token malformé ou signature invalide → re-login
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload, None

    except ExpiredSignatureError:
        logger.info("JWT token expired", extra={"event": "jwt_expired"})
        return None, "expired"

    except JWTError as exc:
        logger.warning("JWT decode error", extra={"event": "jwt_invalid", "error": str(exc)})
        return None, "invalid"


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Compatibilité avec l'ancienne signature — retourne payload ou None.
    Utiliser decode_token_full() pour distinguer expiré vs invalide.
    """
    payload, _ = decode_token_full(token)
    return payload


def decode_refresh_token(token: str) -> Tuple[Optional[Dict[str, Any]], DecodeError]:
    """
    Décode un refresh token et vérifie qu'il porte bien type="refresh".

    Un access token valide mais présenté sur /auth/refresh est rejeté comme
    "invalid" — les deux types de tokens ne sont pas interchangeables.

    NOTE sécurité : il n'existe pas (encore) de liste de révocation pour les
    refresh tokens. Si un compte est suspendu par un admin, son refresh token
    reste valide jusqu'à expiration naturelle (7 jours par défaut). C'est
    acceptable en démo mais à corriger avant un déploiement en production
    (ex : table `revoked_tokens` ou vérification du statut utilisateur, ce
    que fait déjà l'endpoint /auth/refresh en re-lisant le statut en base).
    """
    payload, error = decode_token_full(token)
    if error is not None:
        return None, error
    if payload.get("type") != "refresh":
        logger.warning("Token presented to refresh flow is not a refresh token", extra={"event": "jwt_wrong_type"})
        return None, "invalid"
    return payload, None