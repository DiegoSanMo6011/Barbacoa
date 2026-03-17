from fastapi import APIRouter, Depends, HTTPException, Request
from core.audit import log_audit_event
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles
from models.schemas import GastoOut, GastoCreate

router = APIRouter()

@router.get("", response_model=list[GastoOut])
def listar_gastos(user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    res = sb.table("gastos").select("*").eq("tenant_id", settings.TENANT_ID).order("fecha", desc=True).execute()
    return res.data or []

@router.post("", response_model=GastoOut, status_code=201)
def registrar_gasto(gasto: GastoCreate, request: Request, user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    
    # 1. Registrar gasto
    payload = gasto.model_dump()
    payload["tenant_id"] = settings.TENANT_ID
    
    res = sb.table("gastos").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Error al registrar el gasto")
        
    gasto_creado = res.data[0]
    
    # 2. Si es en efectivo y hay caja abierta, restar de caja chica (Misma logica que POS-Inventory)
    if payload["metodo_pago"] == "EFECTIVO":
        corte_activo = sb.table("cortes_caja").select("id").eq("tenant_id", settings.TENANT_ID).eq("status", "ABIERTO").execute()
        if corte_activo.data:
            monto = float(payload["monto"])
            sb.rpc("ajustar_caja_chica", {"p_tenant_id": settings.TENANT_ID, "p_monto": -monto}).execute()
        
    log_audit_event("finanzas.gasto_registrado", request=request, user=user, metadata={"monto": gasto.monto, "concepto": gasto.concepto})
    return gasto_creado
