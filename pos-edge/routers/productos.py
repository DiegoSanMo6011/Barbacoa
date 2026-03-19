"""
Router: Catálogo de productos con modificadores
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from core.audit import log_audit_event
from models.schemas import (
    CatalogoOut,
    ProductoCreate,
    ProductoUpdate,
    PlantillaOpcionCreate,
    PlantillaOpcionUpdate,
)
from core.supabase_client import get_supabase
from core.config import settings
from core.security import require_roles

router = APIRouter()

_TEMPLATE_CONFIG: dict[str, list[dict[str, Any]]] = {
    "TACO": [
        {
            "nombre": "Tipo de Tortilla",
            "obligatorio": True,
            "seleccion_max": 1,
            "orden": 10,
            "opciones": [
                {"nombre": "Maíz", "precio_delta": 0, "es_default": True, "orden": 10},
                {"nombre": "Harina", "precio_delta": 3, "es_default": False, "orden": 20},
                {"nombre": "Hecha a mano", "precio_delta": 5, "es_default": False, "orden": 30},
            ],
        },
        {
            "nombre": "Preparación",
            "obligatorio": False,
            "seleccion_max": 2,
            "orden": 20,
            "opciones": [
                {"nombre": "Con todo", "precio_delta": 0, "es_default": True, "orden": 10},
                {"nombre": "Sin cebolla", "precio_delta": 0, "es_default": False, "orden": 20},
                {"nombre": "Sin cilantro", "precio_delta": 0, "es_default": False, "orden": 30},
                {"nombre": "Pura carne", "precio_delta": 0, "es_default": False, "orden": 40},
            ],
        },
        {
            "nombre": "Extras",
            "obligatorio": False,
            "seleccion_max": 3,
            "orden": 30,
            "opciones": [
                {"nombre": "Queso", "precio_delta": 15, "es_default": False, "orden": 10},
                {"nombre": "Aguacate", "precio_delta": 10, "es_default": False, "orden": 20},
                {"nombre": "Doble copia", "precio_delta": 5, "es_default": False, "orden": 30},
            ],
        },
    ],
    "TORTA": [
        {
            "nombre": "Tipo de Pan",
            "obligatorio": True,
            "seleccion_max": 1,
            "orden": 10,
            "opciones": [
                {"nombre": "Telera", "precio_delta": 0, "es_default": True, "orden": 10},
                {"nombre": "Bolillo", "precio_delta": 0, "es_default": False, "orden": 20},
                {"nombre": "Baguette", "precio_delta": 15, "es_default": False, "orden": 30},
            ],
        },
        {
            "nombre": "Preparación",
            "obligatorio": False,
            "seleccion_max": 3,
            "orden": 20,
            "opciones": [
                {"nombre": "Con todo", "precio_delta": 0, "es_default": True, "orden": 10},
                {"nombre": "Sin mayonesa", "precio_delta": 0, "es_default": False, "orden": 20},
                {"nombre": "Sin cebolla", "precio_delta": 0, "es_default": False, "orden": 30},
            ],
        },
        {
            "nombre": "Extras",
            "obligatorio": False,
            "seleccion_max": 2,
            "orden": 30,
            "opciones": [
                {"nombre": "Extra carne", "precio_delta": 30, "es_default": False, "orden": 10},
                {"nombre": "Queso extra", "precio_delta": 20, "es_default": False, "orden": 20},
                {"nombre": "Aguacate", "precio_delta": 10, "es_default": False, "orden": 30},
            ],
        },
    ],
}


def _normalizar_tipo(tipo: str | None) -> str:
    if tipo in ("TACO", "TORTA"):
        return tipo
    return "NINGUNA"


def _normalizar_nombre(valor: str | None) -> str:
    return " ".join((valor or "").strip().lower().split())


def _es_pastel_personalizable(nombre: str | None) -> bool:
    return _normalizar_nombre(nombre) == "pastel personalizable"


def _nombre_grupos_template(tipo: str) -> list[str]:
    tipo_norm = _normalizar_tipo(tipo)
    if tipo_norm not in _TEMPLATE_CONFIG:
        raise HTTPException(status_code=400, detail="Plantilla inválida. Usa TACO o TORTA")
    return [g["nombre"] for g in _TEMPLATE_CONFIG[tipo_norm]]


def _upsert_grupo(sb: Any, grupo: dict[str, Any]) -> int:
    payload = {
        "tenant_id": settings.TENANT_ID,
        "nombre": grupo["nombre"],
        "obligatorio": grupo["obligatorio"],
        "seleccion_max": grupo["seleccion_max"],
        "orden": grupo["orden"],
        "activo": True,
    }
    result = sb.table("modificador_grupos").upsert(payload, on_conflict="tenant_id,nombre").execute()
    rows = result.data or []
    if not rows:
        rows = (
            sb.table("modificador_grupos")
            .select("id")
            .eq("tenant_id", settings.TENANT_ID)
            .eq("nombre", grupo["nombre"])
            .limit(1)
            .execute()
            .data
            or []
        )
    if not rows:
        raise HTTPException(status_code=500, detail=f"No se pudo crear grupo {grupo['nombre']}")
    return int(rows[0]["id"])


def _upsert_opciones_grupo(sb: Any, grupo_id: int, opciones: list[dict[str, Any]]) -> None:
    for opcion in opciones:
        payload = {
            "tenant_id": settings.TENANT_ID,
            "grupo_id": grupo_id,
            "nombre": opcion["nombre"],
            "precio_delta": opcion["precio_delta"],
            "es_default": opcion["es_default"],
            "orden": opcion["orden"],
            "activo": True,
        }
        sb.table("modificador_opciones").upsert(payload, on_conflict="grupo_id,nombre").execute()


def _aplicar_template_personalizacion(sb: Any, producto_id: int, tipo: str) -> None:
    tipo = _normalizar_tipo(tipo)
    sb.table("producto_modificador_grupos").delete().eq("tenant_id", settings.TENANT_ID).eq("producto_id", producto_id).execute()

    if tipo == "NINGUNA":
        return

    grupos_cfg = _TEMPLATE_CONFIG.get(tipo, [])
    asignaciones: list[dict[str, Any]] = []
    for grupo in grupos_cfg:
        grupo_id = _upsert_grupo(sb, grupo)
        _upsert_opciones_grupo(sb, grupo_id, grupo["opciones"])
        asignaciones.append(
            {
                "tenant_id": settings.TENANT_ID,
                "producto_id": producto_id,
                "grupo_id": grupo_id,
                "orden": grupo["orden"],
            }
        )

    if asignaciones:
        sb.table("producto_modificador_grupos").upsert(asignaciones, on_conflict="producto_id,grupo_id").execute()


def _asegurar_template_base(sb: Any, tipo: str) -> None:
    tipo_norm = _normalizar_tipo(tipo)
    if tipo_norm not in _TEMPLATE_CONFIG:
        return
    for grupo in _TEMPLATE_CONFIG[tipo_norm]:
        grupo_id = _upsert_grupo(sb, grupo)
        _upsert_opciones_grupo(sb, grupo_id, grupo["opciones"])


def _validar_pastel_abierto_unico(sb: Any, exclude_producto_id: int | None = None) -> None:
    query = (
        sb.table("productos")
        .select("id")
        .eq("tenant_id", settings.TENANT_ID)
        .eq("activo", True)
        .eq("precio_abierto", True)
    )
    if exclude_producto_id is not None:
        query = query.neq("id", exclude_producto_id)
    exists = query.limit(1).execute().data or []
    if exists:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un pastel personalizable con costo abierto. Solo se permite uno.",
        )


def _aplicar_reglas_precio_abierto(
    sb: Any,
    nombre: str,
    precio_abierto: bool,
    personalizacion_tipo: str,
    exclude_producto_id: int | None = None,
) -> tuple[str, bool, str]:
    tipo = _normalizar_tipo(personalizacion_tipo)
    nombre_out = nombre
    if _es_pastel_personalizable(nombre):
        nombre_out = "Pastel personalizable"

    if precio_abierto and not _es_pastel_personalizable(nombre_out):
        raise HTTPException(
            status_code=400,
            detail='El único producto con costo abierto permitido es "Pastel personalizable".',
        )

    if _es_pastel_personalizable(nombre_out) and not precio_abierto:
        raise HTTPException(
            status_code=400,
            detail='"Pastel personalizable" debe mantenerse con costo abierto.',
        )

    if precio_abierto:
        tipo = "NINGUNA"  # nunca lleva modificadores
        _validar_pastel_abierto_unico(sb, exclude_producto_id=exclude_producto_id)

    return nombre_out, precio_abierto, tipo


def _normalizar_catalogo(payload: Any) -> CatalogoOut:
    """Evita fallos cuando la RPC retorna null en arrays anidados."""
    if not isinstance(payload, dict):
        return CatalogoOut(categorias=[])

    categorias = payload.get("categorias")
    if not isinstance(categorias, list):
        return CatalogoOut(categorias=[])

    for categoria in categorias:
        if not isinstance(categoria, dict):
            continue
        productos = categoria.get("productos")
        if not isinstance(productos, list):
            categoria["productos"] = []
            continue

        for producto in productos:
            if not isinstance(producto, dict):
                continue
            producto["precio_abierto"] = bool(producto.get("precio_abierto", False))
            producto["personalizacion_tipo"] = _normalizar_tipo(producto.get("personalizacion_tipo"))
            modificadores = producto.get("modificadores")
            if not isinstance(modificadores, list):
                producto["modificadores"] = []
                continue

            for grupo in modificadores:
                if not isinstance(grupo, dict):
                    continue
                if not isinstance(grupo.get("opciones"), list):
                    grupo["opciones"] = []

    return CatalogoOut(categorias=categorias)

@router.get("", response_model=CatalogoOut)
def get_catalogo(_user=Depends(require_roles("CAJERO", "ADMIN"))):
    """Retorna el catálogo completo con productos simples."""
    sb = get_supabase()
    
    # 1. Fetch direct from legacy productos table
    res = sb.table("productos").select("*").eq("activo", True).order("orden_catalogo").execute()
    if not res.data:
         return CatalogoOut(categorias=[])
         
    # 2. Group by text 'categoria' field
    cat_map = {}
    for p in res.data:
        c_name = p.get("categoria") or "GENERAL"
        if c_name not in cat_map:
            cat_map[c_name] = {"id": len(cat_map) + 1, "nombre": c_name, "orden": len(cat_map) * 10, "productos": []}
            
        prod_format = {
            "id": p["id"],
            "nombre": p["nombre"],
            "precio_base": p["precio"],
            "precio_abierto": p.get("precio_abierto", False),
            "personalizacion_tipo": "NINGUNA",
            "descripcion": p.get("descripcion", ""),
            "orden_catalogo": p.get("orden_catalogo", 1000),
            "modificadores": []
        }
        cat_map[c_name]["productos"].append(prod_format)
        
    categorias_formateadas = list(cat_map.values())
    return CatalogoOut(categorias=categorias_formateadas)


@router.get("/plantillas/{tipo}")
def obtener_plantilla(tipo: str, _user=Depends(require_roles("ADMIN"))):
    """Retorna una plantilla vacía porque el esquema Single-Store no soporta modificadores."""
    tipo_norm = _normalizar_tipo(tipo.upper())
    return {
        "tipo": tipo_norm,
        "grupos": []
    }


@router.post("/plantillas/{tipo}/opciones", status_code=201)
def crear_opcion_plantilla(tipo: str, body: PlantillaOpcionCreate, request: Request, user=Depends(require_roles("ADMIN"))):
    raise HTTPException(status_code=400, detail="Esta versión Single-Store no soporta edición de modificadores.")


@router.patch("/plantillas/{tipo}/opciones/{opcion_id}")
def actualizar_opcion_plantilla(
    tipo: str,
    opcion_id: int,
    body: PlantillaOpcionUpdate,
    request: Request,
    user=Depends(require_roles("ADMIN")),
):
    raise HTTPException(status_code=400, detail="Esta versión Single-Store no soporta edición de modificadores.")


@router.delete("/plantillas/{tipo}/opciones/{opcion_id}", status_code=204)
def eliminar_opcion_plantilla(tipo: str, opcion_id: int, request: Request, user=Depends(require_roles("ADMIN"))):
    raise HTTPException(status_code=400, detail="Esta versión Single-Store no soporta edición de modificadores.")


@router.post("", status_code=201)
def crear_producto(body: ProductoCreate, request: Request, user=Depends(require_roles("ADMIN"))):
    """Crea un nuevo producto en el catálogo."""
    sb = get_supabase()
    data = body.model_dump()
    data["precio"] = data["precio_base"]  # compatibilidad con esquema POS Full
    # Remove tenant_id
    
    result = sb.table("productos").insert(data).execute()
    if not result.data:
        log_audit_event("catalogo.producto_error", request=request, user=user, metadata={"action": "crear"})
        raise HTTPException(status_code=400, detail="Error al crear producto")

    creado = result.data[0]
    log_audit_event(
        "catalogo.producto_creado",
        request=request,
        user=user,
        metadata={"producto_id": int(creado["id"]), "nombre": creado.get("nombre")},
    )
    return creado


@router.patch("/{producto_id}")
def actualizar_producto(producto_id: int, body: ProductoUpdate, request: Request, user=Depends(require_roles("ADMIN"))):
    """Actualiza un producto existente."""
    sb = get_supabase()
    data = {"nombre": body.nombre, "categoria": body.categoria, "activo": body.activo}
    data = {k: v for k, v in data.items() if v is not None}

    if "precio_base" in body.model_dump() and body.precio_base is not None:
        data["precio"] = body.precio_base  # mantener columnas sincronizadas

    result = (
        sb.table("productos")
        .update(data)
        .eq("id", producto_id)
        .execute()
    )
    if not result.data:
        log_audit_event("catalogo.producto_error", request=request, user=user, metadata={"action": "actualizar", "producto_id": producto_id})
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    log_audit_event(
        "catalogo.producto_actualizado",
        request=request,
        user=user,
        metadata={"producto_id": producto_id, "campos": sorted(data.keys())},
    )
    return result.data[0]


@router.delete("/{producto_id}", status_code=204)
def eliminar_producto(producto_id: int, request: Request, user=Depends(require_roles("ADMIN"))):
    """Desactiva (soft delete) un producto."""
    sb = get_supabase()
    sb.table("productos").update({"activo": False}).eq("id", producto_id).execute()
    log_audit_event(
        "catalogo.producto_eliminado",
        request=request,
        user=user,
        metadata={"producto_id": producto_id},
    )
