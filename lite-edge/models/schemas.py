"""
DTOs para el Edge Lite — Pydantic v2
"""
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


# ============================================================
# Auth
# ============================================================
class UnlockRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=8)
    rol: Literal["CAJERO", "ADMIN"] = "CAJERO"
    usuario: Optional[str] = Field(default=None, min_length=3, max_length=40)

class UnlockResponse(BaseModel):
    token: str
    rol: str
    usuario: Optional[str] = None
    session_id: str
    expires_at: datetime


# ============================================================
# Inventario
# ============================================================
class InsumoOut(BaseModel):
    id: str
    nombre: str
    unidad: str
    stock_actual: float
    stock_minimo: float
    activo: bool

class InsumoCreate(BaseModel):
    nombre: str = Field(min_length=1)
    unidad: str = Field(default="pz")
    stock_minimo: float = Field(ge=0, default=0)

class InsumoUpdate(BaseModel):
    nombre: Optional[str] = None
    unidad: Optional[str] = None
    stock_actual: Optional[float] = Field(ge=0, default=None)
    stock_minimo: Optional[float] = Field(ge=0, default=None)
    activo: Optional[bool] = None

class MovimientoInventarioCreate(BaseModel):
    insumo_id: str
    tipo: Literal["ENTRADA", "SALIDA"]
    cantidad: float
    motivo: str
    referencia_id: Optional[str] = None

class MovimientoInventarioOut(BaseModel):
    id: str
    insumo_id: str
    tipo: str
    cantidad: float
    motivo: Optional[str] = None
    referencia_id: Optional[str] = None
    created_at: datetime

class RecetaOut(BaseModel):
    id: str
    producto_id: int
    insumo_id: str
    cantidad: float

class RecetaCreate(BaseModel):
    producto_id: int
    insumo_id: str
    cantidad: float = Field(gt=0)


# ============================================================
# Gastos y Propinas
# ============================================================
class GastoCreate(BaseModel):
    monto: float = Field(gt=0)
    concepto: str = Field(min_length=1)
    categoria: str = Field(min_length=1)
    nota: Optional[str] = None
    metodo_pago: Literal["EFECTIVO", "TARJETA", "TRANSFER"] = "EFECTIVO"

class GastoOut(BaseModel):
    id: str
    monto: float
    concepto: str
    categoria: str
    nota: Optional[str] = None
    metodo_pago: str
    fecha: datetime

class PropinaCreate(BaseModel):
    monto: float = Field(ge=0)
    mesero_id: Optional[str] = None
    mesero_nombre_snapshot: Optional[str] = None
    fuente: Literal["MESA", "BARRA", "DOMICILIO", "NO_ESPECIFICADO"] = "NO_ESPECIFICADO"
    comanda_id: Optional[str] = None

class PropinaOut(BaseModel):
    id: str
    monto: float
    mesero_id: Optional[str] = None
    mesero_nombre_snapshot: Optional[str] = None
    fuente: str
    comanda_id: Optional[str] = None
    fecha: datetime


# ============================================================
# Catálogo — Modificadores
# ============================================================
class OpcionOut(BaseModel):
    id: int
    nombre: str
    precio_delta: float
    es_default: bool
    orden: int

class GrupoModificadorOut(BaseModel):
    grupo_id: int
    grupo_nombre: str
    obligatorio: bool
    seleccion_max: int
    orden: int
    opciones: list[OpcionOut] = []

class ProductoOut(BaseModel):
    id: int
    nombre: str
    precio_base: float
    precio_abierto: bool = False
    personalizacion_tipo: Literal["NINGUNA", "TACO", "TORTA"] = "NINGUNA"
    descripcion: Optional[str]
    orden_catalogo: int
    modificadores: list[GrupoModificadorOut] = []

class CategoriaOut(BaseModel):
    id: int
    nombre: str
    orden: int
    productos: list[ProductoOut] = []

class CatalogoOut(BaseModel):
    categorias: list[CategoriaOut] = []


# ============================================================
# Catálogo — Create/Update
# ============================================================
class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    precio_base: float = Field(ge=0)
    categoria_id: Optional[int] = None
    descripcion: Optional[str] = None
    orden_catalogo: int = Field(default=1000)
    precio_abierto: bool = False
    personalizacion_tipo: Literal["NINGUNA", "TACO", "TORTA"] = "NINGUNA"

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    precio_base: Optional[float] = Field(None, ge=0)
    categoria_id: Optional[int] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None
    orden_catalogo: Optional[int] = None
    precio_abierto: Optional[bool] = None
    personalizacion_tipo: Optional[Literal["NINGUNA", "TACO", "TORTA"]] = None


# ============================================================
# Plantillas de personalización (edición ligera)
# ============================================================
class PlantillaOpcionCreate(BaseModel):
    grupo_nombre: str = Field(min_length=1, max_length=100)
    nombre: str = Field(min_length=1, max_length=100)
    precio_delta: float = 0
    es_default: bool = False
    orden: int = 100

class PlantillaOpcionUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    precio_delta: Optional[float] = None
    es_default: Optional[bool] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None


# ============================================================
# Ventas
# ============================================================
class ModificadorSeleccionado(BaseModel):
    grupo: str
    opcion: str
    delta: float

class ItemVentaIn(BaseModel):
    producto_id: int
    nombre_snapshot: str
    precio_unitario: float   # precio_base + sum(deltas)
    cantidad: int = Field(ge=1, default=1)
    modificadores_snapshot: list[ModificadorSeleccionado] = []
    notas_item: Optional[str] = None

class PagoIn(BaseModel):
    metodo: Literal["EFECTIVO", "TARJETA", "TRANSFER"]
    monto: float = Field(ge=0)
    recibido: Optional[float] = None  # solo para efectivo

class VentaCreate(BaseModel):
    client_sale_id: UUID
    items: list[ItemVentaIn] = Field(min_length=1)
    pago: PagoIn
    total: float = Field(ge=0)
    notas: Optional[str] = None

class VentaOut(BaseModel):
    comanda_id: str
    folio: int
    total: float
    cambio: float
    deduplicated: bool = False


# ============================================================
# Corte de Caja
# ============================================================
class AbrirCorteRequest(BaseModel):
    caja_chica_inicial: float = Field(ge=0, default=0)

class CerrarCorteRequest(BaseModel):
    efectivo_reportado: float = Field(ge=0)
    notas: Optional[str] = None

class CorteOut(BaseModel):
    id: str
    fecha: str
    status: str
    caja_chica_inicial: float
    total_ventas: float
    total_efectivo: float
    total_tarjeta: float
    total_transfer: float
    efectivo_teorico: float
    efectivo_contado: Optional[float]
    diferencia: Optional[float]
    folio_corte: Optional[str]
    abierto_at: datetime
    cerrado_at: Optional[datetime]


# ============================================================
# Status
# ============================================================
class StatusOut(BaseModel):
    status: str
    version: str
    tenant_id: str
    tenant_slug: str
    supabase_online: bool
    timestamp: datetime
