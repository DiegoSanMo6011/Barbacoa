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
    res = sb.table("gastos").select("*").order("created_at", desc=True).execute()
    return res.data or []

@router.post("", response_model=GastoOut, status_code=201)
def registrar_gasto(gasto: GastoCreate, request: Request, user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    
    # 1. Registrar gasto
    payload = gasto.model_dump()
    
    res = sb.table("gastos").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Error al registrar el gasto")
        
    gasto_creado = res.data[0]
    
    # 2. Si es en efectivo y hay caja abierta, restar de caja chica (Misma logica que POS-Inventory)
    if payload.get("metodo_pago") == "EFECTIVO":
        corte_activo = sb.table("cierres_caja").select("id, total_gastos").eq("estado", "ABIERTO").order("created_at", desc=True).limit(1).execute()
        if corte_activo.data:
            cierre = corte_activo.data[0]
            nuevo_gasto = float(cierre.get("total_gastos", 0)) + float(gasto.monto)
            sb.table("cierres_caja").update({"total_gastos": nuevo_gasto}).eq("id", cierre["id"]).execute()
        
    log_audit_event("finanzas.gasto_registrado", request=request, user=user, metadata={"monto": gasto.monto, "concepto": gasto.concepto})
    return gasto_creado
