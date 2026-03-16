"""
Router: Corte de Caja (Jornada)
Reutiliza las RPCs del POS Full via Supabase
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from core.audit import log_audit_event
from models.schemas import AbrirCorteRequest, CerrarCorteRequest, CorteOut
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles
import datetime

router = APIRouter()

@router.get("", response_model=CorteOut | None)
def get_jornada_activa(_user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Retorna la jornada activa de hoy, o None si no hay."""
    sb = get_supabase()
    result = sb.rpc("get_jornada_activa", {"p_tenant_id": settings.TENANT_ID}).execute()
    if not result.data:
        return None
    row = result.data[0]
    return CorteOut(
        id=str(row["id"]),
        fecha=str(row["fecha"]),
        status=row["status"],
        caja_chica_inicial=row.get("caja_chica_inicial", 0),
        total_ventas=row.get("total_ventas", 0),
        total_efectivo=row.get("total_efectivo", 0),
        total_tarjeta=row.get("total_tarjeta", 0),
        total_transfer=row.get("total_transfer", 0),
        efectivo_teorico=row.get("efectivo_teorico", 0),
        efectivo_contado=row.get("efectivo_contado"),
        diferencia=row.get("diferencia"),
        folio_corte=row.get("folio_corte"),
        abierto_at=row["created_at"],
        cerrado_at=row.get("fecha_cierre"),
    )


@router.post("/abrir", status_code=201)
def abrir_jornada(body: AbrirCorteRequest, request: Request, user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Abre una nueva jornada de caja para hoy."""
    sb = get_supabase()
    usuario = str(user.get("usuario") or user.get("rol") or "CAJERO")
    result = sb.rpc(
        "abrir_jornada",
        {
            "p_tenant_id": settings.TENANT_ID,
            "p_caja_chica": body.caja_chica_inicial,
            "p_usuario": usuario,
        },
    ).execute()
    if not result.data:
        log_audit_event("corte.abrir_error", request=request, user=user)
        raise HTTPException(status_code=400, detail="No se pudo abrir la jornada")
    jornada_id = str(result.data)
    log_audit_event(
        "corte.abierta",
        request=request,
        user=user,
        metadata={"jornada_id": jornada_id, "caja_chica_inicial": body.caja_chica_inicial},
    )
    return {"jornada_id": jornada_id}


@router.post("/cerrar")
def cerrar_jornada(body: CerrarCorteRequest, request: Request, user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Cierra la jornada activa y genera el folio de corte."""
    sb = get_supabase()
    # Obtener jornada activa
    jornada = sb.rpc("get_jornada_activa", {"p_tenant_id": settings.TENANT_ID}).execute()
    if not jornada.data:
        log_audit_event("corte.cerrar_error", request=request, user=user, metadata={"detail": "No hay jornada activa"})
        raise HTTPException(status_code=404, detail="No hay jornada activa")

    jornada_id = str(jornada.data[0]["id"])
    folio = f"C{datetime.date.today().strftime('%Y%m%d')}-{jornada_id[:4].upper()}"

    result = sb.rpc(
        "cerrar_jornada",
        {
            "p_cierre_id": jornada_id,
            "p_efectivo_contado": body.efectivo_reportado,
            "p_folio_corte": folio,
            "p_usuario": str(user.get("usuario") or user.get("rol") or "CAJERO"),
        },
    ).execute()

    if not result.data:
        log_audit_event("corte.cerrar_error", request=request, user=user, metadata={"jornada_id": jornada_id})
        raise HTTPException(status_code=400, detail="No se pudo cerrar la jornada")

    log_audit_event(
        "corte.cerrada",
        request=request,
        user=user,
        metadata={"jornada_id": jornada_id, "folio_corte": folio},
    )
    return {"folio_corte": folio, "jornada_id": str(jornada_id)}


@router.post("/reabrir")
def reabrir_jornada(request: Request, user=Depends(require_roles("ADMIN"))):
    """Reabre la última jornada cerrada del día."""
    sb = get_supabase()

    activa = sb.rpc("get_jornada_activa", {"p_tenant_id": settings.TENANT_ID}).execute()
    if activa.data and str(activa.data[0].get("status", "")).upper() == "ABIERTA":
        log_audit_event("corte.reabrir_error", request=request, user=user, metadata={"detail": "Ya existe jornada abierta"})
        raise HTTPException(status_code=409, detail="Ya existe una jornada abierta")

    hoy = datetime.date.today().isoformat()
    cerrada = (
        sb.table("cierres_caja")
        .select("id")
        .eq("tenant_id", settings.TENANT_ID)
        .eq("fecha", hoy)
        .eq("status", "CERRADA")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not cerrada.data:
        log_audit_event("corte.reabrir_error", request=request, user=user, metadata={"detail": "No hay jornada cerrada"})
        raise HTTPException(status_code=404, detail="No hay jornada cerrada hoy para reabrir")

    jornada_id = str(cerrada.data[0]["id"])

    payload = {
        "status": "ABIERTA",
        "fecha_cierre": None,
        "efectivo_contado": None,
        "diferencia": None,
        "folio_corte": None,
    }
    try:
        result = (
            sb.table("cierres_caja")
            .update(payload)
            .eq("id", jornada_id)
            .eq("tenant_id", settings.TENANT_ID)
            .execute()
        )
    except Exception:
        # Fallback mínimo en instalaciones donde no existan algunos campos de cierre.
        result = (
            sb.table("cierres_caja")
            .update({"status": "ABIERTA"})
            .eq("id", jornada_id)
            .eq("tenant_id", settings.TENANT_ID)
            .execute()
        )

    if not result.data:
        log_audit_event("corte.reabrir_error", request=request, user=user, metadata={"jornada_id": jornada_id})
        raise HTTPException(status_code=400, detail="No se pudo reabrir la jornada")

    log_audit_event("corte.reabierta", request=request, user=user, metadata={"jornada_id": jornada_id})
    return {"jornada_id": jornada_id, "status": "ABIERTA"}
