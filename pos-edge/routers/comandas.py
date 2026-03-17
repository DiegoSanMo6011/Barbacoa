"""
Router: Ventas rápidas
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from core.audit import log_audit_event
from models.schemas import VentaCreate, VentaOut
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles
from datetime import date

router = APIRouter()


def _extract_error_detail(exc: Exception) -> str:
    text = str(exc)
    if "No hay jornada ABIERTA" in text:
        return "No hay jornada abierta. Abre la jornada antes de cobrar."
    if "Total inconsistente" in text:
        return "Total inconsistente en venta."
    if "Metodo de pago inválido" in text:
        return "Método de pago inválido."
    return text


def _status_for_error(detail: str) -> int:
    if "jornada abierta" in detail.lower():
        return 409
    return 400


@router.post("", response_model=VentaOut, status_code=201)
def crear_venta(
    body: VentaCreate,
    request: Request,
    user=Depends(require_roles("CAJERO", "ADMIN")),
):
    """Registra una venta y actualiza la jornada activa."""
    sb = get_supabase()

    items_json = [
        {
            "producto_id":            item.producto_id,
            "nombre_snapshot":        item.nombre_snapshot,
            "precio_unitario":        item.precio_unitario,
            "cantidad":               item.cantidad,
            "modificadores_snapshot": [m.model_dump() for m in item.modificadores_snapshot],
            "notas_item":             item.notas_item,
        }
        for item in body.items
    ]

    pago_json = {
        "metodo":   body.pago.metodo,
        "monto":    body.pago.monto,
        "recibido": body.pago.recibido,
    }

    try:
        result = sb.rpc(
            "crear_venta_lite",
            {
                "p_tenant_id": settings.TENANT_ID,
                "p_client_sale_id": str(body.client_sale_id),
                "p_items":     items_json,
                "p_pago":      pago_json,
                "p_total":     body.total,
                "p_notas":     body.notas,
            },
        ).execute()
    except Exception as exc:
        detail = _extract_error_detail(exc)
        log_audit_event(
            "venta.crear_error",
            request=request,
            user=user,
            metadata={
                "client_sale_id": str(body.client_sale_id),
                "detail": detail,
            },
        )
        raise HTTPException(status_code=_status_for_error(detail), detail=detail) from exc

    if not result.data:
        log_audit_event(
            "venta.crear_error",
            request=request,
            user=user,
            metadata={"client_sale_id": str(body.client_sale_id), "detail": "Error al registrar venta"},
        )
        raise HTTPException(status_code=400, detail="Error al registrar venta")

    salida = VentaOut(**result.data)
    log_audit_event(
        "venta.creada" if not salida.deduplicated else "venta.deduplicada",
        request=request,
        user=user,
        metadata={
            "client_sale_id": str(body.client_sale_id),
            "comanda_id": salida.comanda_id,
            "folio": salida.folio,
            "total": salida.total,
        },
    )
    return salida


@router.get("")
def listar_ventas(limit: int = 50, _user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Historial de ventas del día actual."""
    sb = get_supabase()
    hoy = date.today().isoformat()
    result = (
        sb.table("comandas")
        .select("id, folio, total, metodo_pago, status, created_at, notas")
        .eq("tenant_id", settings.TENANT_ID)
        .eq("status", "PAGADA")
        .gte("created_at", hoy)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


@router.get("/{comanda_id}")
def get_venta(comanda_id: str, _user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Detalle de una venta (para reimpresión de ticket)."""
    sb = get_supabase()
    result = (
        sb.table("comandas")
        .select("*, comanda_items(*), comanda_pagos(*)")
        .eq("id", comanda_id)
        .eq("tenant_id", settings.TENANT_ID)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return result.data
