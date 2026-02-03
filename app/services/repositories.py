"""Repositorios de acceso a datos (Supabase).

Cada repositorio encapsula operaciones para una tabla especifica.
Se usa herencia para reutilizar operaciones basicas.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from domain.models import (
    CierreCaja,
    ComandaDraft,
    ComandaItem,
    Gasto,
    Mesero,
    Producto,
    Propina,
)


class SupabaseTable(ABC):
    """Base para repositorios con operaciones comunes."""

    table_name: str

    def __init__(self, client: Any):
        self._client = client

    def _table(self):
        return self._client.table(self.table_name)

    def _insert_one(self, payload: dict) -> dict:
        res = self._table().insert(payload).execute()
        return res.data[0]

    def _insert_many(self, payloads: list[dict]) -> list[dict]:
        if not payloads:
            return []
        res = self._table().insert(payloads).execute()
        return res.data or []

    def _update_one(self, payload: dict, key: str, value: Any) -> dict:
        res = self._table().update(payload).eq(key, value).execute()
        return res.data[0]


class ProductosRepository(SupabaseTable):
    table_name = "productos"

    def list_activos(self) -> list[Producto]:
        rows = self._table().select("*").eq("activo", True).order("categoria").execute().data or []
        return [Producto.from_record(r) for r in rows]

    def list_all(self) -> list[Producto]:
        rows = self._table().select("*").order("categoria").execute().data or []
        return [Producto.from_record(r) for r in rows]

    def create(self, producto: Producto) -> Producto:
        payload = producto.to_record()
        payload.pop("id", None)
        created = self._insert_one(payload)
        return Producto.from_record(created)

    def update_fields(self, producto_id: int, changes: dict) -> Producto:
        updated = self._update_one(changes, "id", producto_id)
        return Producto.from_record(updated)


class MeserosRepository(SupabaseTable):
    table_name = "meseros"

    def list_activos(self) -> list[Mesero]:
        rows = (
            self._table()
            .select("id, nombre, activo")
            .eq("activo", True)
            .order("nombre")
            .execute()
            .data
            or []
        )
        return [Mesero.from_record(r) for r in rows]

    def list_all(self) -> list[Mesero]:
        rows = self._table().select("id, nombre, activo").order("nombre").execute().data or []
        return [Mesero.from_record(r) for r in rows]

    def create(self, mesero: Mesero) -> Mesero:
        payload = mesero.to_record()
        payload.pop("id", None)
        created = self._insert_one(payload)
        return Mesero.from_record(created)

    def update_fields(self, mesero_id: str, changes: dict) -> Mesero:
        updated = self._update_one(changes, "id", mesero_id)
        return Mesero.from_record(updated)


class ComandasRepository(SupabaseTable):
    table_name = "comandas"

    def create(self, comanda: ComandaDraft) -> dict:
        return self._insert_one(comanda.to_record())


class ComandaItemsRepository(SupabaseTable):
    table_name = "comanda_items"

    def insert_many(self, comanda_id: str, items: list[ComandaItem]) -> None:
        payloads = [item.to_record(comanda_id=comanda_id) for item in items]
        self._insert_many(payloads)


class GastosRepository(SupabaseTable):
    table_name = "gastos"

    def create(self, gasto: Gasto) -> dict:
        return self._insert_one(gasto.to_record())

    def list_by_range(self, desde: str, hasta: str) -> list[dict]:
        rows = (
            self._table()
            .select("*")
            .gte("created_at", desde)
            .lte("created_at", hasta)
            .order("created_at")
            .execute()
            .data
            or []
        )
        return rows


class PropinasRepository(SupabaseTable):
    table_name = "propinas"

    def create(self, propina: Propina) -> dict:
        return self._insert_one(propina.to_record())

    def list_by_range(self, desde: str, hasta: str) -> list[dict]:
        rows = (
            self._table()
            .select("*")
            .gte("fecha", desde)
            .lte("fecha", hasta)
            .order("fecha")
            .execute()
            .data
            or []
        )
        return rows


class CierresRepository(SupabaseTable):
    table_name = "cierres_caja"

    def get_by_fecha(self, fecha_iso: str) -> dict | None:
        res = self._table().select("*").eq("fecha", fecha_iso).execute()
        return res.data[0] if res.data else None

    def create(self, cierre: CierreCaja) -> dict:
        return self._insert_one(cierre.to_record())
