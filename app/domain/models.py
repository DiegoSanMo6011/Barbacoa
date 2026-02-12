"""Modelos de dominio para el POS.

Incluye dataclasses, herencia y conversiones a dict para persistencia.
Se usan validaciones simples para mantener consistencia de datos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any


def _round2(value: float) -> float:
    return round(float(value), 2)


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _coerce_optional_float(value: Any | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


class RecordSerializable(ABC):
    """Contrato para modelos que se persisten como dict."""

    @abstractmethod
    def to_record(self) -> dict:
        raise NotImplementedError


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFER = "TRANSFER"

    @classmethod
    def from_raw(cls, value: str | None) -> "MetodoPago":
        if value is None:
            raise ValueError("metodo_pago es obligatorio")
        normalized = _clean_text(value).upper()
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"metodo_pago invalido: {value}") from exc


_PROPINA_ORIGENES_VALIDOS = {
    MetodoPago.EFECTIVO.value,
    MetodoPago.TARJETA.value,
    MetodoPago.TRANSFER.value,
    "NO_ESPECIFICADO",
}


def _normalize_propina_fuente(value: str | None) -> str:
    fuente = _clean_text(value).upper()
    if fuente in {"", "MANUAL", "COMANDA"}:
        return "NO_ESPECIFICADO"
    if fuente in _PROPINA_ORIGENES_VALIDOS:
        return fuente
    return "NO_ESPECIFICADO"


@dataclass(slots=True)
class Producto(RecordSerializable):
    id: int | None
    nombre: str
    categoria: str
    precio: float
    activo: bool = True
    venta_por_gramo: bool = False
    orden_catalogo: int = 1000

    @classmethod
    def from_inputs(
        cls,
        nombre: str,
        categoria: str,
        precio: float,
        activo: bool = True,
        venta_por_gramo: bool = False,
        orden_catalogo: int = 1000,
    ) -> "Producto":
        nombre_limpio = _clean_text(nombre)
        if not nombre_limpio:
            raise ValueError("nombre es obligatorio")
        categoria_limpia = _clean_text(categoria)
        if not categoria_limpia:
            raise ValueError("categoria es obligatoria")
        if precio is None or float(precio) < 0:
            raise ValueError("precio debe ser >= 0")
        try:
            orden = int(orden_catalogo)
        except Exception:
            orden = 1000
        if orden < 0:
            raise ValueError("orden_catalogo debe ser >= 0")
        return cls(
            id=None,
            nombre=nombre_limpio,
            categoria=categoria_limpia,
            precio=_round2(float(precio)),
            activo=bool(activo),
            venta_por_gramo=bool(venta_por_gramo),
            orden_catalogo=orden,
        )

    @classmethod
    def from_record(cls, data: dict) -> "Producto":
        return cls(
            id=int(data["id"]) if data.get("id") is not None else None,
            nombre=data.get("nombre") or "",
            categoria=data.get("categoria") or "GENERAL",
            precio=_round2(float(data.get("precio") or 0)),
            activo=bool(data.get("activo", True)),
            venta_por_gramo=bool(data.get("venta_por_gramo", False)),
            orden_catalogo=int(data.get("orden_catalogo") or 1000),
        )

    def to_record(self) -> dict:
        record = {
            "nombre": _clean_text(self.nombre),
            "categoria": _clean_text(self.categoria) or "GENERAL",
            "precio": _round2(self.precio),
            "activo": bool(self.activo),
            "orden_catalogo": int(self.orden_catalogo),
        }
        if self.venta_por_gramo:
            record["venta_por_gramo"] = True
        if self.id is not None:
            record["id"] = int(self.id)
        return record


@dataclass(slots=True)
class Mesero(RecordSerializable):
    id: str | None
    nombre: str
    activo: bool = True

    @classmethod
    def from_inputs(cls, nombre: str, activo: bool = True) -> "Mesero":
        nombre_limpio = _clean_text(nombre)
        if not nombre_limpio:
            raise ValueError("nombre es obligatorio")
        return cls(id=None, nombre=nombre_limpio, activo=bool(activo))

    @classmethod
    def from_record(cls, data: dict) -> "Mesero":
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre") or "",
            activo=bool(data.get("activo", True)),
        )

    def to_record(self) -> dict:
        record = {"nombre": _clean_text(self.nombre), "activo": bool(self.activo)}
        if self.id is not None:
            record["id"] = self.id
        return record


@dataclass(slots=True)
class Usuario(RecordSerializable):
    id: str | None
    nombre: str
    usuario: str
    password_hash: str
    rol: str
    activo: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_record(cls, data: dict) -> "Usuario":
        rol = _clean_text(data.get("rol")).upper()
        if rol == "ADMIN":
            rol = "DUENIO"
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre") or "",
            usuario=data.get("usuario") or "",
            password_hash=data.get("password_hash") or "",
            rol=rol or "GERENTE",
            activo=bool(data.get("activo", True)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_record(self) -> dict:
        rol = _clean_text(self.rol).upper()
        if rol == "ADMIN":
            rol = "DUENIO"
        record = {
            "nombre": _clean_text(self.nombre),
            "usuario": _clean_text(self.usuario),
            "password_hash": _clean_text(self.password_hash),
            "rol": rol,
            "activo": bool(self.activo),
        }
        if self.id is not None:
            record["id"] = self.id
        if self.created_at:
            record["created_at"] = self.created_at
        if self.updated_at:
            record["updated_at"] = self.updated_at
        return record


@dataclass(slots=True)
class ComandaItem(RecordSerializable):
    producto_id: int
    nombre_snapshot: str
    precio_unitario: float
    cantidad: int
    subtotal: float

    @classmethod
    def from_raw(cls, data: dict) -> "ComandaItem":
        return cls(
            producto_id=int(data["producto_id"]),
            nombre_snapshot=data.get("nombre_snapshot") or "",
            precio_unitario=_round2(float(data.get("precio_unitario") or 0)),
            cantidad=int(data.get("cantidad") or 0),
            subtotal=_round2(float(data.get("subtotal") or 0)),
        )

    def to_record(self, *, comanda_id: str | None = None) -> dict:
        record = {
            "producto_id": int(self.producto_id),
            "nombre_snapshot": _clean_text(self.nombre_snapshot),
            "precio_unitario": _round2(self.precio_unitario),
            "cantidad": int(self.cantidad),
            "subtotal": _round2(self.subtotal),
        }
        if comanda_id:
            record["comanda_id"] = comanda_id
        return record


@dataclass(slots=True)
class ComandaDraft(RecordSerializable):
    mesero: str
    metodo_pago: MetodoPago
    total: float
    recibido: float | None
    cambio: float | None
    items: list[ComandaItem]
    propina: float | None = None

    @classmethod
    def from_raw(
        cls,
        mesero: str,
        metodo_pago: str,
        total: float,
        recibido: float | None,
        cambio: float | None,
        items: list[dict] | None = None,
        propina: float | None = None,
    ) -> "ComandaDraft":
        items = items or []
        parsed_items = [ComandaItem.from_raw(it) for it in items]
        return cls(
            mesero=_clean_text(mesero),
            metodo_pago=MetodoPago.from_raw(metodo_pago),
            total=_round2(float(total)),
            recibido=_coerce_optional_float(recibido),
            cambio=_coerce_optional_float(cambio),
            items=parsed_items,
            propina=_coerce_optional_float(propina),
        )

    def to_record(self) -> dict:
        return {
            "mesero": _clean_text(self.mesero),
            "metodo_pago": self.metodo_pago.value,
            "total": _round2(self.total),
            "recibido": None if self.recibido is None else _round2(self.recibido),
            "cambio": None if self.cambio is None else _round2(self.cambio),
            "status": "PAGADA",
        }

    def to_offline_payload(self) -> dict:
        return {
            "mesero": _clean_text(self.mesero),
            "metodo_pago": self.metodo_pago.value,
            "total": _round2(self.total),
            "recibido": self.recibido,
            "cambio": self.cambio,
            "items": [item.to_record() for item in self.items],
            "propina": self.propina,
        }


@dataclass(slots=True)
class MovimientoCaja(RecordSerializable, ABC):
    monto: float

    def monto_redondeado(self) -> float:
        return _round2(self.monto)


@dataclass(slots=True)
class Gasto(MovimientoCaja):
    concepto: str
    categoria: str
    nota: str | None = None
    metodo_pago: str = MetodoPago.EFECTIVO.value

    @classmethod
    def from_inputs(
        cls,
        concepto: str,
        categoria: str,
        monto: float,
        nota: str | None = None,
        metodo_pago: str = MetodoPago.EFECTIVO.value,
    ) -> "Gasto":
        concepto_limpio = _clean_text(concepto)
        if not concepto_limpio:
            raise ValueError("concepto es obligatorio")
        categoria_limpia = _clean_text(categoria)
        if not categoria_limpia:
            raise ValueError("categoria es obligatoria")
        metodo_limpio = _clean_text(metodo_pago)
        if not metodo_limpio:
            raise ValueError("metodo_pago es obligatorio")
        if monto is None or float(monto) <= 0:
            raise ValueError("monto debe ser > 0")
        return cls(
            monto=_round2(float(monto)),
            concepto=concepto_limpio,
            categoria=categoria_limpia,
            nota=_clean_text(nota) if isinstance(nota, str) and _clean_text(nota) else None,
            metodo_pago=metodo_limpio,
        )

    def to_record(self) -> dict:
        return {
            "concepto": _clean_text(self.concepto),
            "categoria": _clean_text(self.categoria),
            "monto": self.monto_redondeado(),
            "nota": _clean_text(self.nota) if self.nota else None,
            "metodo_pago": _clean_text(self.metodo_pago),
        }


@dataclass(slots=True)
class Propina(MovimientoCaja):
    mesero_id: str | None = None
    mesero_nombre_snapshot: str | None = None
    fuente: str = "NO_ESPECIFICADO"
    comanda_id: str | None = None

    @classmethod
    def from_inputs(
        cls,
        monto: float,
        mesero_id: str | None = None,
        mesero_nombre_snapshot: str | None = None,
        fuente: str = "NO_ESPECIFICADO",
        comanda_id: str | None = None,
    ) -> "Propina":
        if monto is None or float(monto) < 0:
            raise ValueError("monto debe ser >= 0")
        fuente_limpia = _normalize_propina_fuente(fuente)
        nombre = _clean_text(mesero_nombre_snapshot) if mesero_nombre_snapshot else None
        return cls(
            monto=_round2(float(monto)),
            mesero_id=mesero_id,
            mesero_nombre_snapshot=nombre,
            fuente=fuente_limpia,
            comanda_id=comanda_id,
        )

    def to_record(self) -> dict:
        return {
            "monto": self.monto_redondeado(),
            "mesero_id": self.mesero_id,
            "mesero_nombre_snapshot": _clean_text(self.mesero_nombre_snapshot)
            if self.mesero_nombre_snapshot
            else None,
            "fuente": _normalize_propina_fuente(self.fuente),
            "comanda_id": self.comanda_id,
        }


@dataclass(slots=True)
class CierreCaja(RecordSerializable):
    fecha: date
    total_ventas: float
    total_gastos: float
    neto: float
    efectivo_reportado: float
    diferencia_efectivo: float
    notas: str | None = None

    def to_record(self) -> dict:
        return {
            "fecha": self.fecha.isoformat(),
            "total_ventas": _round2(self.total_ventas),
            "total_gastos": _round2(self.total_gastos),
            "neto": _round2(self.neto),
            "efectivo_reportado": _round2(self.efectivo_reportado),
            "diferencia_efectivo": _round2(self.diferencia_efectivo),
            "notas": _clean_text(self.notas) if isinstance(self.notas, str) and _clean_text(self.notas) else None,
        }
