from fastapi import APIRouter, Depends, HTTPException, Request
from core.audit import log_audit_event
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles
from models.schemas import PropinaOut, PropinaCreate

router = APIRouter()

@router.get("", response_model=list[PropinaOut])
def listar_propinas(user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    res = sb.table("propinas").select("*").eq("tenant_id", settings.TENANT_ID).order("fecha", desc=True).execute()
    return res.data or []

@router.post("", response_model=PropinaOut, status_code=201)
def registrar_propina(propina: PropinaCreate, request: Request, user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    payload = propina.model_dump()
    payload["tenant_id"] = settings.TENANT_ID
    
    res = sb.table("propinas").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Error al registrar propina")
        
    propina_creada = res.data[0]
    log_audit_event("finanzas.propina_registrada", request=request, user=user, metadata={"monto": propina.monto, "fuente": propina.fuente})
    return propina_creada
