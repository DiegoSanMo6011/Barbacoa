"""Dual-write hacia Autonoma SaaS (fire-and-forget).

Replica operaciones de escritura del POS hacia la base de datos
multi-tenant de Autonoma para que el dashboard web muestre datos
en tiempo real. Si falla, solo loguea un warning — nunca bloquea
la operacion principal.

Usa httpx directo en vez de supabase-py porque el venv tiene
supabase-py 2.6.0 que no acepta keys formato nuevo (sb_secret_...).
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import httpx

from .settings import (
    AUTONOMA_PRODUCTO_OFFSET,
    AUTONOMA_SUPABASE_KEY,
    AUTONOMA_SUPABASE_URL,
    AUTONOMA_SUCURSAL_ID,
    AUTONOMA_TENANT_ID,
    SUPABASE_TIMEOUT_SECONDS,
)

_logger = logging.getLogger("barbacoa.autonoma")

# Tablas que se replican a Autonoma.
SYNC_TABLES: set[str] = {
    "comandas",
    "comanda_items",
    "comanda_pagos",
    "comanda_correcciones",
    "ticket_historial",
    "gastos",
    "propinas",
    "cierres_caja",
    "productos",
    "meseros",
}


def _fire_and_forget(fn: Any, *args: Any) -> None:
    """Ejecuta *fn* en un daemon thread; captura toda excepcion."""
    def _wrapper() -> None:
        try:
            fn(*args)
        except Exception:
            _logger.warning("Autonoma sync error en %s", fn.__name__, exc_info=True)
    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()


class AutonomaClient:
    """Cliente secundario que replica escrituras a Autonoma via REST."""

    def __init__(self) -> None:
        self._base_url = AUTONOMA_SUPABASE_URL.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": AUTONOMA_SUPABASE_KEY,
            "Authorization": f"Bearer {AUTONOMA_SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        self._timeout = SUPABASE_TIMEOUT_SECONDS
        self._tenant_id: str = AUTONOMA_TENANT_ID
        self._sucursal_id: str | None = AUTONOMA_SUCURSAL_ID
        self._offset: int = AUTONOMA_PRODUCTO_OFFSET
        _logger.info("Autonoma dual-write habilitado (tenant=%s)", self._tenant_id)

    def _post(self, table: str, payload: Any) -> None:
        """POST a Supabase REST API (insert)."""
        url = f"{self._base_url}/{table}"
        resp = httpx.post(url, headers=self._headers, json=payload, timeout=self._timeout)
        resp.raise_for_status()

    def _patch(self, table: str, changes: dict, key: str, value: Any) -> None:
        """PATCH a Supabase REST API (update)."""
        url = f"{self._base_url}/{table}?{key}=eq.{value}"
        resp = httpx.patch(url, headers=self._headers, json=changes, timeout=self._timeout)
        resp.raise_for_status()

    def _delete(self, table: str, key: str, value: Any) -> None:
        """DELETE a Supabase REST API."""
        url = f"{self._base_url}/{table}?{key}=eq.{value}"
        resp = httpx.delete(url, headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # API publica (llamada desde repositories.py)
    # ------------------------------------------------------------------

    def replicate_insert(self, table: str, payload: dict, result: dict) -> None:
        """Replica un INSERT. *result* es la fila devuelta por la BD primaria."""
        if table not in SYNC_TABLES:
            return
        _fire_and_forget(self._do_insert, table, payload, result)

    def replicate_insert_many(self, table: str, payloads: list[dict], results: list[dict]) -> None:
        if table not in SYNC_TABLES or not payloads:
            return
        _fire_and_forget(self._do_insert_many, table, payloads, results)

    def replicate_update(self, table: str, changes: dict, key: str, value: Any) -> None:
        if table not in SYNC_TABLES:
            return
        _fire_and_forget(self._do_update, table, changes, key, value)

    def replicate_delete(self, table: str, key: str, value: Any) -> None:
        if table not in SYNC_TABLES:
            return
        _fire_and_forget(self._do_delete, table, key, value)

    def replicate_comanda(
        self,
        comanda_result: dict,
        items_payloads: list[dict],
        pagos_payloads: list[dict],
        propinas_payloads: list[dict],
    ) -> None:
        """Replica comanda completa (comanda + items + pagos + propinas) en un solo thread."""
        _fire_and_forget(
            self._do_comanda_batch,
            comanda_result,
            items_payloads,
            pagos_payloads,
            propinas_payloads,
        )

    # ------------------------------------------------------------------
    # Transformaciones
    # ------------------------------------------------------------------

    # Tablas que requieren sucursal_id NOT NULL.
    _SUCURSAL_TABLES = {"comandas", "cierres_caja", "productos"}
    # Columnas de Miranda que no existen en Autonoma.
    _DROP_COLUMNS: dict[str, set[str]] = {
        "comanda_items": {"created_at"},
        "gastos": {"fecha"},
    }

    def _inject_tenant(self, payload: dict, table: str | None = None) -> dict:
        p = dict(payload)
        p["tenant_id"] = self._tenant_id
        if table in self._SUCURSAL_TABLES and self._sucursal_id:
            p["sucursal_id"] = self._sucursal_id
        return p

    def _transform(self, table: str, payload: dict, result: dict) -> dict:
        p = self._inject_tenant(payload, table)

        # Quitar columnas que no existen en Autonoma.
        for col in self._DROP_COLUMNS.get(table, ()):
            p.pop(col, None)

        # Tablas con UUID PK: preservar el id generado por la BD primaria.
        if table not in ("productos", "comanda_items"):
            p["id"] = result.get("id", p.get("id"))

        # Tablas con id SERIAL: quitar id para auto-gen en Autonoma.
        if table == "productos":
            p.pop("id", None)

        if table == "comanda_items":
            p.pop("id", None)
            # Offsetear producto_id para que coincida con Autonoma.
            if self._offset and "producto_id" in p:
                try:
                    p["producto_id"] = int(p["producto_id"]) + self._offset
                except (TypeError, ValueError):
                    pass

        if table == "comandas":
            p["client_sale_id"] = result.get("id")

        return p

    # ------------------------------------------------------------------
    # Operaciones internas (corren en daemon thread)
    # ------------------------------------------------------------------

    def _do_insert(self, table: str, payload: dict, result: dict) -> None:
        transformed = self._transform(table, payload, result)
        self._post(table, transformed)
        _logger.debug("Autonoma INSERT %s OK (id=%s)", table, result.get("id"))

    def _do_insert_many(self, table: str, payloads: list[dict], results: list[dict]) -> None:
        transformed = []
        for payload, result in zip(payloads, results):
            transformed.append(self._transform(table, payload, result))
        if transformed:
            self._post(table, transformed)
            _logger.debug("Autonoma INSERT %s x%d OK", table, len(transformed))

    def _do_update(self, table: str, changes: dict, key: str, value: Any) -> None:
        self._patch(table, changes, key, value)
        _logger.debug("Autonoma UPDATE %s OK (%s=%s)", table, key, value)

    def _do_delete(self, table: str, key: str, value: Any) -> None:
        self._delete(table, key, value)
        _logger.debug("Autonoma DELETE %s OK (%s=%s)", table, key, value)

    def _do_comanda_batch(
        self,
        comanda_result: dict,
        items_payloads: list[dict],
        pagos_payloads: list[dict],
        propinas_payloads: list[dict],
    ) -> None:
        """Inserta comanda + items + pagos + propinas secuencialmente."""
        comanda_id = comanda_result.get("id")

        # 1. Comanda
        comanda_p = self._inject_tenant(comanda_result, "comandas")
        comanda_p["client_sale_id"] = comanda_id
        self._post("comandas", comanda_p)

        # 2. Items
        if items_payloads:
            items_t = []
            for item in items_payloads:
                it = self._inject_tenant(item, "comanda_items")
                it.pop("id", None)
                it["comanda_id"] = comanda_id
                if self._offset and "producto_id" in it:
                    try:
                        it["producto_id"] = int(it["producto_id"]) + self._offset
                    except (TypeError, ValueError):
                        pass
                items_t.append(it)
            self._post("comanda_items", items_t)

        # 3. Pagos
        if pagos_payloads:
            pagos_t = [self._inject_tenant(p, "comanda_pagos") for p in pagos_payloads]
            for p in pagos_t:
                p["comanda_id"] = comanda_id
            self._post("comanda_pagos", pagos_t)

        # 4. Propinas
        if propinas_payloads:
            propinas_t = [self._inject_tenant(p, "propinas") for p in propinas_payloads]
            for p in propinas_t:
                p["comanda_id"] = comanda_id
            self._post("propinas", propinas_t)

        _logger.debug(
            "Autonoma comanda batch OK (id=%s, items=%d, pagos=%d, propinas=%d)",
            comanda_id,
            len(items_payloads),
            len(pagos_payloads),
            len(propinas_payloads),
        )
