"""Repositorios de acceso a datos (Supabase).

Cada repositorio encapsula operaciones para una tabla especifica.
Se usa herencia para reutilizar operaciones basicas.
"""

from __future__ import annotations

from abc import ABC
from datetime import datetime, timezone
from typing import Any

from domain.models import (
    CierreCaja,
    ComandaDraft,
    ComandaItem,
    Gasto,
    Mesero,
    Producto,
    Propina,
    Usuario,
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

    def _delete_one(self, key: str, value: Any) -> dict | None:
        res = self._table().delete().eq(key, value).execute()
        rows = res.data or []
        if not rows:
            return None
        return rows[0]


class ProductosRepository(SupabaseTable):
    table_name = "productos"

    def list_activos(self) -> list[Producto]:
        try:
            rows = (
                self._table()
                .select("*")
                .eq("activo", True)
                .order("orden_catalogo")
                .order("categoria")
                .order("nombre")
                .execute()
                .data
                or []
            )
        except Exception:
            rows = (
                self._table()
                .select("*")
                .eq("activo", True)
                .order("categoria")
                .order("nombre")
                .execute()
                .data
                or []
            )
        return [Producto.from_record(r) for r in rows]

    def list_all(self) -> list[Producto]:
        try:
            rows = (
                self._table()
                .select("*")
                .order("orden_catalogo")
                .order("categoria")
                .order("nombre")
                .execute()
                .data
                or []
            )
        except Exception:
            rows = (
                self._table()
                .select("*")
                .order("categoria")
                .order("nombre")
                .execute()
                .data
                or []
            )
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

    def delete(self, mesero_id: str) -> None:
        self._delete_one("id", mesero_id)


class ComandasRepository(SupabaseTable):
    table_name = "comandas"

    def create(self, comanda: ComandaDraft) -> dict:
        payload = comanda.to_record()
        retry_payload = dict(payload)
        for _ in range(3):
            try:
                return self._insert_one(retry_payload)
            except Exception as exc:
                msg = str(exc).lower()
                if "column" not in msg and "schema cache" not in msg:
                    raise
                changed = False
                if "mesa" in msg and "mesa" in retry_payload:
                    retry_payload.pop("mesa", None)
                    changed = True
                if "status" in msg and "status" in retry_payload:
                    retry_payload.pop("status", None)
                    changed = True
                if not changed:
                    raise
        return self._insert_one(retry_payload)

    def list_historial(
        self,
        *,
        desde_iso: str,
        hasta_iso: str,
        folio: int | None = None,
        mesero: str | None = None,
        mesa: str | None = None,
    ) -> list[dict]:
        columns = (
            "id, folio, created_at, mesero, mesa, total, metodo_pago, status, "
            "cancelada_at, cancelada_por, cancelacion_motivo"
        )
        query = (
            self._table()
            .select(columns)
            .gte("created_at", desde_iso)
            .lte("created_at", hasta_iso)
            .order("created_at", desc=True)
            .limit(600)
        )
        if folio is not None:
            query = query.eq("folio", folio)
        if mesero:
            query = query.ilike("mesero", f"%{mesero}%")
        if mesa:
            query = query.ilike("mesa", f"%{mesa}%")
        try:
            rows = query.execute().data or []
        except Exception as exc:
            msg = str(exc).lower()
            if ("column" in msg or "schema cache" in msg) and any(
                token in msg for token in ("mesa", "cancelada_", "cancelacion_motivo", "status")
            ):
                if mesa:
                    # La columna mesa no existe en esquema legacy; no se puede filtrar.
                    return []
                columns_legacy = "id, folio, created_at, mesero, total, metodo_pago"
                legacy_query = (
                    self._table()
                    .select(columns_legacy)
                    .gte("created_at", desde_iso)
                    .lte("created_at", hasta_iso)
                    .order("created_at", desc=True)
                    .limit(600)
                )
                if folio is not None:
                    legacy_query = legacy_query.eq("folio", folio)
                if mesero:
                    legacy_query = legacy_query.ilike("mesero", f"%{mesero}%")
                rows = legacy_query.execute().data or []
                for row in rows:
                    row.setdefault("mesa", None)
                    row.setdefault("cancelada_at", None)
                    row.setdefault("cancelada_por", None)
                    row.setdefault("cancelacion_motivo", None)
                    row.setdefault("status", "PAGADA")
            else:
                raise
        return rows

    def get_by_id(self, comanda_id: str) -> dict | None:
        rows = self._table().select("*").eq("id", comanda_id).limit(1).execute().data or []
        if not rows:
            return None
        return rows[0]

    def update_fields(self, comanda_id: str, changes: dict) -> dict:
        return self._update_one(changes, "id", comanda_id)


class ComandaItemsRepository(SupabaseTable):
    table_name = "comanda_items"

    def insert_many(self, comanda_id: str, items: list[ComandaItem]) -> None:
        payloads = [item.to_record(comanda_id=comanda_id) for item in items]
        self._insert_many(payloads)

    def list_by_comanda(self, comanda_id: str) -> list[dict]:
        rows = (
            self._table()
            .select("id, comanda_id, producto_id, nombre_snapshot, precio_unitario, cantidad, subtotal")
            .eq("comanda_id", comanda_id)
            .order("id")
            .execute()
            .data
            or []
        )
        return rows

    def replace_for_comanda(self, comanda_id: str, items: list[ComandaItem]) -> None:
        self._table().delete().eq("comanda_id", comanda_id).execute()
        self.insert_many(comanda_id, items)


class ComandaPagosRepository(SupabaseTable):
    table_name = "comanda_pagos"

    def insert_many(self, comanda_id: str, pagos: list[dict]) -> list[dict]:
        payloads: list[dict] = []
        for idx, pago in enumerate(pagos):
            payloads.append(
                {
                    "comanda_id": comanda_id,
                    "orden": int(pago.get("orden") or idx + 1),
                    "metodo_pago": str(pago.get("metodo_pago") or "").strip().upper(),
                    "monto": float(pago.get("monto") or 0),
                    "recibido": pago.get("recibido"),
                    "cambio": pago.get("cambio"),
                    "propina": float(pago.get("propina") or 0),
                }
            )
        return self._insert_many(payloads)

    def list_by_comanda(self, comanda_id: str) -> list[dict]:
        rows = (
            self._table()
            .select("id, comanda_id, orden, metodo_pago, monto, recibido, cambio, propina")
            .eq("comanda_id", comanda_id)
            .order("orden")
            .execute()
            .data
            or []
        )
        return rows

    def list_by_comandas(self, comanda_ids: list[str]) -> list[dict]:
        if not comanda_ids:
            return []
        rows = (
            self._table()
            .select("id, comanda_id, orden, metodo_pago, monto, recibido, cambio, propina")
            .in_("comanda_id", comanda_ids)
            .order("orden")
            .execute()
            .data
            or []
        )
        return rows

    def update_fields(self, pago_id: str, changes: dict) -> dict:
        return self._update_one(changes, "id", pago_id)
        
    def replace_for_comanda(self, comanda_id: str, pagos: list[dict]) -> list[dict]:
        self._table().delete().eq("comanda_id", comanda_id).execute()
        return self.insert_many(comanda_id, pagos)


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

    def update_fields(self, gasto_id: str, changes: dict) -> dict:
        return self._update_one(changes, "id", gasto_id)

    def delete(self, gasto_id: str) -> None:
        self._delete_one("id", gasto_id)


class PropinasRepository(SupabaseTable):
    table_name = "propinas"

    def create(self, propina: Propina) -> dict:
        return self._insert_one(propina.to_record())

    def get_by_id(self, propina_id: str) -> dict | None:
        rows = self._table().select("*").eq("id", propina_id).limit(1).execute().data or []
        if not rows:
            return None
        return rows[0]

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

    def update_fields(self, propina_id: str, changes: dict) -> dict:
        return self._update_one(changes, "id", propina_id)

    def delete(self, propina_id: str) -> None:
        self._delete_one("id", propina_id)


class CierresRepository(SupabaseTable):
    table_name = "cierres_caja"

    def get_by_fecha(self, fecha_iso: str) -> dict | None:
        res = self._table().select("*").eq("fecha", fecha_iso).execute()
        return res.data[0] if res.data else None

    def create(self, cierre: CierreCaja) -> dict:
        return self._insert_one(cierre.to_record())


class ComandaCorreccionesRepository(SupabaseTable):
    table_name = "comanda_correcciones"

    def create(
        self,
        *,
        comanda_id: str,
        motivo: str,
        before_payload: dict,
        after_payload: dict,
        corregido_por: str,
    ) -> dict:
        payload = {
            "comanda_id": comanda_id,
            "motivo": motivo,
            "before_payload": before_payload,
            "after_payload": after_payload,
            "corregido_por": corregido_por,
        }
        return self._insert_one(payload)


class TicketHistorialRepository(SupabaseTable):
    table_name = "ticket_historial"

    def list_by_comanda(self, comanda_id: str) -> list[dict]:
        rows = (
            self._table()
            .select("id, comanda_id, version, tipo, ticket_text, created_at, created_by")
            .eq("comanda_id", comanda_id)
            .order("version")
            .execute()
            .data
            or []
        )
        return rows

    def create(
        self,
        *,
        comanda_id: str,
        version: int,
        tipo: str,
        ticket_text: str,
        created_by: str | None = None,
    ) -> dict:
        payload = {
            "comanda_id": comanda_id,
            "version": int(version),
            "tipo": str(tipo).strip().upper(),
            "ticket_text": ticket_text,
            "created_by": created_by,
        }
        return self._insert_one(payload)


class UsuariosRepository(SupabaseTable):
    table_name = "usuarios"

    @staticmethod
    def _normalize_role(role: str) -> str:
        normalized = (role or "").strip().upper()
        if normalized in {"DUEÑO", "DUENO"}:
            normalized = "DUENIO"
        if normalized == "ADMIN":
            return "DUENIO"
        if normalized not in {"GERENTE", "DUENIO"}:
            raise ValueError(f"rol invalido: {role}")
        return normalized

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_by_role(self, role: str) -> Usuario | None:
        role_norm = self._normalize_role(role)
        roles = [role_norm]
        if role_norm == "DUENIO":
            roles.append("ADMIN")

        if len(roles) == 1:
            query = self._table().select("*").eq("rol", roles[0])
        else:
            query = self._table().select("*").in_("rol", roles)

        rows = query.limit(1).execute().data or []
        if not rows:
            return None
        return Usuario.from_record(rows[0])

    def list_roles(self) -> list[Usuario]:
        rows = (
            self._table()
            .select("*")
            .in_("rol", ["GERENTE", "DUENIO", "ADMIN"])
            .order("rol")
            .execute()
            .data
            or []
        )
        by_role: dict[str, Usuario] = {}
        for row in rows:
            user = Usuario.from_record(row)
            if user.rol not in by_role:
                by_role[user.rol] = user
        return [by_role[r] for r in ("GERENTE", "DUENIO") if r in by_role]

    def set_role_pin(
        self,
        role: str,
        password_hash: str,
        *,
        nombre: str | None = None,
        usuario: str | None = None,
        activo: bool | None = None,
    ) -> Usuario:
        role_norm = self._normalize_role(role)
        existing = self.get_by_role(role_norm)

        if existing:
            payload = {
                "password_hash": password_hash,
                "updated_at": self._utcnow_iso(),
            }
            if nombre is not None:
                payload["nombre"] = (nombre or "").strip()
            if usuario is not None:
                payload["usuario"] = (usuario or "").strip()
            if activo is not None:
                payload["activo"] = bool(activo)
            updated = self._update_one(payload, "id", existing.id)
            return Usuario.from_record(updated)

        defaults = {
            "GERENTE": ("Gerente", "GERENTE"),
            "DUENIO": ("Dueño", "DUENIO"),
        }
        default_nombre, default_usuario = defaults[role_norm]
        payload = {
            "nombre": (nombre or default_nombre).strip(),
            "usuario": (usuario or default_usuario).strip(),
            "password_hash": password_hash,
            "rol": role_norm,
            "activo": True if role_norm == "DUENIO" else bool(activo if activo is not None else True),
        }
        created = self._insert_one(payload)
        return Usuario.from_record(created)

    def set_role_active(self, role: str, active: bool) -> Usuario:
        role_norm = self._normalize_role(role)
        if role_norm == "DUENIO" and not active:
            raise ValueError("No se puede desactivar DUEÑO")

        existing = self.get_by_role(role_norm)
        if not existing or not existing.id:
            raise ValueError(f"No existe usuario para rol {role_norm}")

        payload = {"activo": bool(active), "updated_at": self._utcnow_iso()}
        updated = self._update_one(payload, "id", existing.id)
        return Usuario.from_record(updated)

    def migrate_admin_to_duenio(self) -> int:
        now_iso = self._utcnow_iso()
        admin_rows = (
            self._table()
            .select("id, nombre, usuario, password_hash, activo, updated_at")
            .eq("rol", "ADMIN")
            .execute()
            .data
            or []
        )
        if not admin_rows:
            return 0

        duenio_rows = (
            self._table()
            .select("id")
            .eq("rol", "DUENIO")
            .execute()
            .data
            or []
        )

        primary_admin = admin_rows[0]
        if duenio_rows:
            primary_duenio_id = duenio_rows[0].get("id")
            if primary_duenio_id:
                payload = {
                    "nombre": primary_admin.get("nombre") or "Dueño",
                    "usuario": primary_admin.get("usuario") or "DUENIO",
                    "password_hash": primary_admin.get("password_hash") or "",
                    "activo": bool(primary_admin.get("activo", True)),
                    "updated_at": now_iso,
                }
                self._table().update(payload).eq("id", primary_duenio_id).execute()
            for row in admin_rows:
                rid = row.get("id")
                if rid:
                    self._table().delete().eq("id", rid).execute()
            return len(admin_rows)

        primary_admin_id = primary_admin.get("id")
        if primary_admin_id:
            self._table().update({"rol": "DUENIO", "updated_at": now_iso}).eq("id", primary_admin_id).execute()
        for row in admin_rows[1:]:
            rid = row.get("id")
            if rid:
                self._table().delete().eq("id", rid).execute()
        return len(admin_rows)
