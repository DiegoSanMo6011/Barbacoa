"""
Registro en memoria de sesiones activas por tenant.

Modelo actual:
- Nodo único (1 instancia Edge)
- Persistencia en memoria (se limpia al reiniciar proceso)
"""
from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass


@dataclass
class SessionRecord:
    session_id: str
    tenant_id: str
    rol: str
    usuario: str | None
    expires_at: dt.datetime


_LOCK = threading.Lock()
_ACTIVE: dict[str, dict[str, SessionRecord]] = {}


def _now_utc() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _normalize_expiration(expires_at: dt.datetime) -> dt.datetime:
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=dt.timezone.utc)
    return expires_at.astimezone(dt.timezone.utc)


def _purge_expired_locked(now: dt.datetime) -> None:
    tenants_to_drop: list[str] = []
    for tenant_id, sessions in _ACTIVE.items():
        expired = [sid for sid, rec in sessions.items() if rec.expires_at <= now]
        for sid in expired:
            sessions.pop(sid, None)
        if not sessions:
            tenants_to_drop.append(tenant_id)
    for tenant_id in tenants_to_drop:
        _ACTIVE.pop(tenant_id, None)


def register_session(
    *,
    tenant_id: str,
    session_id: str,
    rol: str,
    usuario: str | None,
    expires_at: dt.datetime,
    max_active_sessions: int,
) -> tuple[bool, int]:
    now = _now_utc()
    normalized_exp = _normalize_expiration(expires_at)
    with _LOCK:
        _purge_expired_locked(now)
        sessions = _ACTIVE.setdefault(tenant_id, {})
        if session_id in sessions:
            sessions[session_id] = SessionRecord(
                session_id=session_id,
                tenant_id=tenant_id,
                rol=rol,
                usuario=usuario,
                expires_at=normalized_exp,
            )
            return True, len(sessions)

        if len(sessions) >= max_active_sessions:
            return False, len(sessions)

        sessions[session_id] = SessionRecord(
            session_id=session_id,
            tenant_id=tenant_id,
            rol=rol,
            usuario=usuario,
            expires_at=normalized_exp,
        )
        return True, len(sessions)


def is_session_active(tenant_id: str, session_id: str) -> bool:
    now = _now_utc()
    with _LOCK:
        _purge_expired_locked(now)
        sessions = _ACTIVE.get(tenant_id)
        if not sessions:
            return False
        return session_id in sessions


def revoke_session(tenant_id: str, session_id: str) -> bool:
    with _LOCK:
        sessions = _ACTIVE.get(tenant_id)
        if not sessions:
            return False
        existed = sessions.pop(session_id, None) is not None
        if not sessions:
            _ACTIVE.pop(tenant_id, None)
        return existed


def count_active_sessions(tenant_id: str) -> int:
    now = _now_utc()
    with _LOCK:
        _purge_expired_locked(now)
        sessions = _ACTIVE.get(tenant_id)
        return len(sessions) if sessions else 0


def clear_all_sessions_for_tests() -> None:
    with _LOCK:
        _ACTIVE.clear()
