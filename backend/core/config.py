import logging
import os
import warnings
from functools import lru_cache

logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "change-me-in-production-long-random-string"


class Settings:
    app_version: str = "2.1.0"
    max_file_size: int = 10 * 1024 * 1024

    @property
    def api_key(self) -> str | None:
        return os.environ.get("API_KEY") or None

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def cors_origins(self) -> list[str]:
        raw = os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        )
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def jwt_secret_key(self) -> str:
        key = os.environ.get("JWT_SECRET_KEY", "")
        if key in ("", _DEFAULT_JWT_SECRET):
            warning_msg = (
                "JWT_SECRET_KEY non configure (ou laisse a sa valeur par defaut) — "
                "tous les tokens JWT sont forgeables. Definissez une valeur longue "
                "et aleatoire via la variable d'environnement JWT_SECRET_KEY avant "
                "tout deploiement en production."
            )
            warnings.warn(warning_msg, RuntimeWarning, stacklevel=2)
            logger.warning(warning_msg)
        return key or _DEFAULT_JWT_SECRET

    @property
    def jwt_algorithm(self) -> str:
        return os.environ.get("JWT_ALGORITHM", "HS256")

    @property
    def smtp_host(self) -> str | None:
        val = os.environ.get("SMTP_HOST")
        return val.strip() if val else None

    @property
    def smtp_port(self) -> int:
        try:
            return int(os.environ.get("SMTP_PORT", "587"))
        except ValueError:
            return 587

    @property
    def smtp_user(self) -> str | None:
        val = os.environ.get("SMTP_USER")
        return val.strip() if val else None

    @property
    def smtp_password(self) -> str | None:
        val = os.environ.get("SMTP_PASSWORD")
        return val.strip() if val else None

    @property
    def smtp_sender(self) -> str | None:
        val = os.environ.get("SMTP_SENDER")
        return val.strip() if val else None

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_sender)


@lru_cache
def get_settings() -> Settings:
    return Settings()