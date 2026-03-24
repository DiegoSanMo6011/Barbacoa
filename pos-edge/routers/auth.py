"""
Router: Auth (PIN simple para Cajero y Admin)
"""
from __future__ import annotations

import datetime
import logging
import re
import threading
import uuid
from collections import deque

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from core.audit import log_audit_event
from core.config import settings
from core.security import get_current_user
from core.session_registry import count_active_sessions, register_session, revoke_session
from models.schemas import UnlockRequest, UnlockResponse

router = APIRouter()
ALGORITHM = "HS256"
logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_FAILED_ATTEMPTS: dict[str, deque[datetime.datetime]] = {}
_LOCKED_UNTIL: dict[str, datetime.datetime] = {}
_USUARIO_RE = re.compile(r"^[A-Za-z0-9._ -]{3,40}$")


def _key_from_request(request: Request, rol: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{rol}"


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _purge_old_attempts(values: deque[datetime.datetime], now: datetime.datetime) -> None:
    window = datetime.timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
    while values and (now - values[0]) > window:
        values.popleft()


def _assert_not_locked(key: str, now: datetime.datetime) -> None:
    locked_until = _LOCKED_UNTIL.get(key)
    if not locked_until:
        return
    if locked_until <= now:
        _LOCKED_UNTIL.pop(key, None)
        _FAILED_ATTEMPTS.pop(key, None)
        return
    retry_after = int((locked_until - now).total_seconds())
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos. Intenta nuevamente en {retry_after}s",
        headers={"Retry-After": str(retry_after)},
    )


def _register_failed_attempt(key: str, now: datetime.datetime) -> None:
    attempts = _FAILED_ATTEMPTS.setdefault(key, deque())
    _purge_old_attempts(attempts, now)
    attempts.append(now)
    if len(attempts) >= settings.AUTH_MAX_ATTEMPTS:
        _LOCKED_UNTIL[key] = now + datetime.timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)


def _clear_attempts(key: str) -> None:
    _FAILED_ATTEMPTS.pop(key, None)
    _LOCKED_UNTIL.pop(key, None)


def _sanitize_usuario(value: str | None) -> str | None:
    if value is None:
        return None
    usuario = " ".join(value.strip().split())
    if not usuario:
        return None
    if not _USUARIO_RE.match(usuario):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Usuario inválido. Usa 3-40 caracteres alfanuméricos.",
        )
    return usuario


@router.post("/unlock", response_model=UnlockResponse)
def unlock(body: UnlockRequest, request: Request):
    now = _now_utc()
    key = _key_from_request(request, body.rol)
    usuario = _sanitize_usuario(body.usuario)

    with _LOCK:
        try:
            _assert_not_locked(key, now)
        except HTTPException:
            log_audit_event(
                "auth.unlock_rate_limited",
                request=request,
                metadata={"rol": body.rol, "usuario": usuario},
            )
            raise

    is_valid_pin = (
        (body.rol == "CAJERO" and body.pin == settings.PIN_CAJERO)
        or (body.rol == "ADMIN" and body.pin == settings.PIN_ADMIN)
    )

    if not is_valid_pin:
        with _LOCK:
            _register_failed_attempt(key, now)
            locked_until = _LOCKED_UNTIL.get(key)
        logger.warning("Unlock fallido ip=%s rol=%s", request.client.host if request.client else "unknown", body.rol)
        log_audit_event(
            "auth.unlock_failed",
            request=request,
            metadata={"rol": body.rol, "usuario": usuario},
        )
        if locked_until and locked_until > now:
            retry_after = int((locked_until - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos. Intenta nuevamente en {retry_after}s",
                headers={"Retry-After": str(retry_after)},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN incorrecto")

    with _LOCK:
        _clear_attempts(key)

    expires = now + datetime.timedelta(hours=settings.JWT_TTL_HOURS)
    session_id = str(uuid.uuid4())
    registered, active_count = register_session(
        tenant_id=settings.TENANT_ID,
        session_id=session_id,
        rol=body.rol,
        usuario=usuario,
        expires_at=expires,
        max_active_sessions=settings.AUTH_MAX_ACTIVE_SESSIONS,
    )
    if not registered:
        log_audit_event(
            "auth.unlock_blocked_max_sessions",
            request=request,
            metadata={
                "rol": body.rol,
                "usuario": usuario,
                "active_sessions": active_count,
                "max_active_sessions": settings.AUTH_MAX_ACTIVE_SESSIONS,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Límite de sesiones activas alcanzado. "
                f"Máximo permitido: {settings.AUTH_MAX_ACTIVE_SESSIONS}. "
                "Cierra sesión en otro dispositivo e intenta de nuevo."
            ),
        )

    token = jwt.encode(
        {
            "sid": session_id,
            "usr": usuario,
            "rol": body.rol,
            "exp": expires,
            "tenant": settings.TENANT_ID,
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    logger.info("Unlock exitoso ip=%s rol=%s", request.client.host if request.client else "unknown", body.rol)
    audit_user = {"rol": body.rol, "usuario": usuario, "session_id": session_id}
    log_audit_event(
        "auth.unlock_success",
        request=request,
        user=audit_user,
        metadata={
            "active_sessions": active_count,
            "max_active_sessions": settings.AUTH_MAX_ACTIVE_SESSIONS,
        },
    )
    return UnlockResponse(token=token, rol=body.rol, usuario=usuario, session_id=session_id, expires_at=expires)


@router.get("/recover_hint", response_model=dict)
def recover_hint():
    """Devuelve la pista del PIN configurada en las variables de entorno para ayudar a los admins."""
    hint = getattr(settings, "PIN_HINT", None)
    if not hint:
        return {"hint": "No hay pista configurada en el sistema. Consulta el archivo .env"}
    return {"hint": hint}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, user: dict[str, str | None] = Depends(get_current_user)):
    tenant = str(user["tenant"])
    session_id = str(user["session_id"])
    revoked = revoke_session(tenant, session_id)
    active_count = count_active_sessions(tenant)
    log_audit_event(
        "auth.logout",
        request=request,
        user=user,
        metadata={"revoked": revoked, "active_sessions": active_count},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
