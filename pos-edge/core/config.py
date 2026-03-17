"""
Configuración del Edge — lee variables de .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    TENANT_ID: str
    TENANT_SLUG: str = "default"
    SECRET_KEY: str = "changeme-in-production"
    PIN_CAJERO: str = "1234"
    PIN_ADMIN: str = "0000"
    ALLOW_ORIGINS: str = "http://localhost:5173,http://localhost:4173"
    JWT_TTL_HOURS: int = 12
    AUTH_MAX_ATTEMPTS: int = 5
    AUTH_LOCKOUT_MINUTES: int = 15
    AUTH_MAX_ACTIVE_SESSIONS: int = 2

settings = Settings()

_DEFAULT_PINS = {"1234", "9999", "0000"}
_DEFAULT_SECRET_HINTS = {"changeme-in-production", "demo", "secret", "test"}


def validate_runtime_security() -> None:
    env = settings.APP_ENV.strip().lower()
    if env not in {"production", "prod"}:
        return

    weak_reasons: list[str] = []
    secret = settings.SECRET_KEY.strip()
    if len(secret) < 32:
        weak_reasons.append("SECRET_KEY debe tener al menos 32 caracteres")
    if any(hint in secret.lower() for hint in _DEFAULT_SECRET_HINTS):
        weak_reasons.append("SECRET_KEY no puede usar valores por defecto")
    if settings.PIN_CAJERO in _DEFAULT_PINS or settings.PIN_ADMIN in _DEFAULT_PINS:
        weak_reasons.append("PIN_CAJERO/PIN_ADMIN no pueden ser valores demo")
    if settings.PIN_CAJERO == settings.PIN_ADMIN:
        weak_reasons.append("PIN_CAJERO y PIN_ADMIN deben ser distintos")
    if settings.AUTH_MAX_ACTIVE_SESSIONS < 1:
        weak_reasons.append("AUTH_MAX_ACTIVE_SESSIONS debe ser al menos 1")

    if weak_reasons:
        reasons = "; ".join(weak_reasons)
        raise RuntimeError(f"Configuración insegura para producción: {reasons}")
