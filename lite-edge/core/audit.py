from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from core.config import settings
from core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def log_audit_event(
    evento: str,
    request: Request | None = None,
    user: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "tenant_id": settings.TENANT_ID,
        "evento": evento,
        "metadata": metadata or {},
    }
    if request is not None:
        payload["ip"] = request.client.host if request.client else None
        payload["request_id"] = getattr(request.state, "request_id", None)
        payload["path"] = request.url.path
    if user:
        payload["rol"] = user.get("rol")
        payload["usuario"] = user.get("usuario")
        payload["session_id"] = user.get("session_id")

    try:
        sb = get_supabase()
        sb.table("audit_eventos").insert(payload).execute()
    except Exception as exc:
        logger.warning("No se pudo registrar audit_evento=%s: %s", evento, exc)
