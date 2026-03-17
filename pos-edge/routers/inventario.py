from fastapi import APIRouter, Depends, HTTPException, Request
from core.audit import log_audit_event
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles
from models.schemas import (
    InsumoOut, InsumoCreate, InsumoUpdate,
    RecetaOut, RecetaCreate,
    MovimientoInventarioOut, MovimientoInventarioCreate
)

router = APIRouter()

# =========================================================
# Insumos
# =========================================================
@router.get("/insumos", response_model=list[InsumoOut])
def listar_insumos(user=Depends(require_roles("CAJERO", "ADMIN"))):
    sb = get_supabase()
    res = sb.table("insumos").select("*").eq("tenant_id", settings.TENANT_ID).eq("activo", True).order("nombre").execute()
    return res.data or []

@router.post("/insumos", response_model=InsumoOut, status_code=201)
def crear_insumo(insumo: InsumoCreate, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    payload = insumo.model_dump()
    payload["tenant_id"] = settings.TENANT_ID
    payload["nombre"] = payload["nombre"].strip()
    
    # Check duplicate
    existing = sb.table("insumos").select("id").eq("tenant_id", settings.TENANT_ID).eq("nombre", payload["nombre"]).eq("activo", True).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail=f"El insumo '{payload['nombre']}' ya existe.")
        
    res = sb.table("insumos").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Error creando insumo")
    
    log_audit_event("inventario.insumo_creado", request=request, user=user, metadata={"nombre": payload["nombre"]})
    return res.data[0]

@router.patch("/insumos/{insumo_id}", response_model=InsumoOut)
def actualizar_insumo(insumo_id: str, changes: InsumoUpdate, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    payload = {k: v for k, v in changes.model_dump().items() if v is not None}
    if not payload:
        res = sb.table("insumos").select("*").eq("id", insumo_id).eq("tenant_id", settings.TENANT_ID).execute()
        return res.data[0] if res.data else {}

    res = sb.table("insumos").update(payload).eq("id", insumo_id).eq("tenant_id", settings.TENANT_ID).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
        
    log_audit_event("inventario.insumo_actualizado", request=request, user=user, metadata={"insumo_id": insumo_id, "campos": list(payload.keys())})
    return res.data[0]

@router.delete("/insumos/{insumo_id}", status_code=204)
def eliminar_insumo(insumo_id: str, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    # Check if used in active recipes
    used = sb.table("recetas").select("id").eq("insumo_id", insumo_id).eq("tenant_id", settings.TENANT_ID).limit(1).execute()
    if used.data:
        raise HTTPException(status_code=400, detail="No se puede eliminar insumo porque es parte de una receta. Primero elimínalo de las recetas.")
        
    sb.table("insumos").update({"activo": False}).eq("id", insumo_id).eq("tenant_id", settings.TENANT_ID).execute()
    log_audit_event("inventario.insumo_eliminado", request=request, user=user, metadata={"insumo_id": insumo_id})

# =========================================================
# Movimientos Stock (Ajustes)
# =========================================================
@router.post("/movimientos", response_model=MovimientoInventarioOut, status_code=201)
def registrar_movimiento(mov: MovimientoInventarioCreate, request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    # Deduplication and locking relies directly on RPC for atomic updates
    try:
        res = sb.rpc("registrar_movimiento_inventario_v2", {
            "p_tenant_id": settings.TENANT_ID,
            "p_insumo_id": mov.insumo_id,
            "p_tipo": mov.tipo,
            "p_cantidad": mov.cantidad,
            "p_motivo": mov.motivo,
            "p_referencia_id": mov.referencia_id
        }).execute()
        
        # Format the response to match the MovimientoInventarioOut Pydantic model
        if res.data and isinstance(res.data, list) and len(res.data) > 0:
            log_audit_event("inventario.movimiento_registrado", request=request, user=user, metadata={"insumo_id": mov.insumo_id, "tipo": mov.tipo, "cantidad": mov.cantidad})
            return res.data[0]
        else:
            raise HTTPException(status_code=500, detail="El RPC no devolvió la fila del movimiento creado")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================================================
# Recetas
# =========================================================
@router.get("/recetas", response_model=list[RecetaOut])
def listar_recetas(user=Depends(require_roles("CAJERO", "ADMIN"))):
    # Depending on client needs, might need joined queries to show names, 
    # but for offline first, the client joins `insumos` and `productos` locally in Dexie.
    sb = get_supabase()
    res = sb.table("recetas").select("*").eq("tenant_id", settings.TENANT_ID).execute()
    return res.data or []

@router.post("/recetas", response_model=list[RecetaOut])
def sincronizar_recetas_producto(producto_id: int, recetas: list[RecetaCreate], request: Request, user=Depends(require_roles("ADMIN"))):
    sb = get_supabase()
    
    # 1. Delete all existing recipes for this product
    sb.table("recetas").delete().eq("tenant_id", settings.TENANT_ID).eq("producto_id", producto_id).execute()
    
    # 2. Insert new
    if not recetas:
        return []
        
    payloads = []
    for r in recetas:
        payloads.append({
            "tenant_id": settings.TENANT_ID,
            "producto_id": r.producto_id,
            "insumo_id": r.insumo_id,
            "cantidad": r.cantidad
        })
        
    res = sb.table("recetas").insert(payloads).execute()
    log_audit_event("inventario.recetas_actualizadas", request=request, user=user, metadata={"producto_id": producto_id, "count": len(payloads)})
    return res.data or []
