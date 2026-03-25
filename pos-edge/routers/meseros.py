from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from core.audit import log_audit_event
from core.supabase_client import get_supabase
from core.security import require_roles

router = APIRouter()

class MeseroCreate(BaseModel):
    nombre: str

class MeseroUpdate(BaseModel):
    activo: bool

@router.get("", response_model=list[dict])
def listar_meseros(user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    res = sb.table("meseros").select("id, nombre, activo, created_at").order("activo", desc=True).order("nombre").execute()
    return res.data or []

@router.post("", status_code=201)
def crear_mesero(mesero: MeseroCreate, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    nombre_limpio = mesero.nombre.strip()
    if not nombre_limpio:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
        
    res = sb.table("meseros").insert({"nombre": nombre_limpio, "activo": True}).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Error al crear el mesero")
        
    log_audit_event("personal.mesero_creado", request=request, user=user, metadata={"nombre": nombre_limpio})
    return res.data[0]

@router.patch("/{mesero_id}")
def actualizar_mesero(mesero_id: str, mesero: MeseroUpdate, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    res = sb.table("meseros").update({"activo": mesero.activo}).eq("id", mesero_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Mesero no encontrado")
        
    log_audit_event("personal.mesero_actualizado", request=request, user=user, metadata={"mesero_id": mesero_id, "activo": mesero.activo})
    return res.data[0]
