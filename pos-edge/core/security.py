"""
Seguridad de API:
- Validación JWT
- Control de rol (CAJERO/ADMIN)
"""
from __future__ import annotations

from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.session_registry import is_session_active

ALGORITHM = "HS256"
VALID_ROLES = {"CAJERO", "ADMIN"}
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, str | None]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token requerido",
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    tenant = str(payload.get("tenant", ""))
    rol = str(payload.get("rol", ""))
    session_id = str(payload.get("sid", ""))
    usuario_raw = payload.get("usr")
    usuario = str(usuario_raw) if usuario_raw is not None else None
    if tenant != settings.TENANT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant inválido en token",
        )
    if rol not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Rol inválido en token",
        )
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida en token",
        )
    if not is_session_active(tenant, session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada o inválida",
        )
    return {"tenant": tenant, "rol": rol, "session_id": session_id, "usuario": usuario}


def require_roles(*roles: str) -> Callable[[dict[str, str | None]], dict[str, str | None]]:
    roles_set = set(roles)

    def _guard(user: dict[str, str | None] = Depends(get_current_user)) -> dict[str, str | None]:
        if user["rol"] not in roles_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return user

    return _guard
