"""Catch-up: sincroniza registros nuevos de Miranda a Autonoma via REST API.

Uso:
    .venv/bin/python3 scripts/catchup_autonoma.py          # dry-run
    .venv/bin/python3 scripts/catchup_autonoma.py --apply   # ejecuta

Lee la ultima comanda migrada en Autonoma y trae todo lo posterior de Miranda.
Usa httpx para Autonoma (keys formato nuevo) y supabase-py para Miranda.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import httpx
from supabase import create_client
from supabase.lib.client_options import ClientOptions

from services.settings import (
    AUTONOMA_PRODUCTO_OFFSET,
    AUTONOMA_SUPABASE_KEY,
    AUTONOMA_SUPABASE_URL,
    AUTONOMA_SUCURSAL_ID,
    AUTONOMA_TENANT_ID,
    SUPABASE_KEY,
    SUPABASE_URL,
)

TENANT_ID = AUTONOMA_TENANT_ID
SUCURSAL_ID = AUTONOMA_SUCURSAL_ID
OFFSET = AUTONOMA_PRODUCTO_OFFSET
SUCURSAL_TABLES = {"comandas", "cierres_caja", "productos"}

# Columnas de Miranda que NO existen en Autonoma — se eliminan antes de insertar.
DROP_COLUMNS: dict[str, set[str]] = {
    "comanda_items": {"created_at"},
    "gastos": {"fecha"},
}
BATCH = 500
TIMEOUT = 30


# --- Miranda (supabase-py) ---

def miranda_client():
    opts = ClientOptions(postgrest_client_timeout=TIMEOUT)
    return create_client(SUPABASE_URL, SUPABASE_KEY, opts)


def miranda_fetch(client, table: str, order: str = "created_at",
                  gt_field: str | None = None, gt_value: str | None = None) -> list[dict]:
    rows, offset = [], 0
    while True:
        q = client.table(table).select("*").order(order).range(offset, offset + BATCH - 1)
        if gt_field and gt_value:
            q = q.gt(gt_field, gt_value)
        batch = q.execute().data or []
        rows.extend(batch)
        if len(batch) < BATCH:
            break
        offset += BATCH
    return rows


def miranda_fetch_by_ids(client, table: str, fk: str, ids: list[str]) -> list[dict]:
    rows = []
    for i in range(0, len(ids), 50):
        batch = client.table(table).select("*").in_(fk, ids[i:i+50]).execute().data or []
        rows.extend(batch)
    return rows


def miranda_count(client, table: str) -> int:
    # Usa select con count para eficiencia.
    rows = []
    offset = 0
    while True:
        batch = client.table(table).select("id").range(offset, offset + 999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return len(rows)


# --- Autonoma (httpx) ---

def autonoma_headers():
    return {
        "apikey": AUTONOMA_SUPABASE_KEY,
        "Authorization": f"Bearer {AUTONOMA_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def autonoma_url(table: str) -> str:
    return f"{AUTONOMA_SUPABASE_URL.rstrip('/')}/rest/v1/{table}"


def autonoma_get(table: str, params: dict | None = None) -> list[dict]:
    hdrs = autonoma_headers()
    hdrs["Prefer"] = ""
    resp = httpx.get(autonoma_url(table), headers=hdrs, params=params or {}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def autonoma_insert(table: str, records: list[dict]) -> None:
    if not records:
        return
    for i in range(0, len(records), 200):
        resp = httpx.post(autonoma_url(table), headers=autonoma_headers(),
                          json=records[i:i+200], timeout=TIMEOUT)
        resp.raise_for_status()


def autonoma_count(table: str) -> int:
    hdrs = autonoma_headers()
    hdrs["Prefer"] = "count=exact"
    hdrs["Range"] = "0-0"
    resp = httpx.get(autonoma_url(table), headers=hdrs,
                     params={"select": "id", "tenant_id": f"eq.{TENANT_ID}"}, timeout=TIMEOUT)
    resp.raise_for_status()
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[-1]) if "/" in cr else 0


def inject(records: list[dict], table: str = "") -> list[dict]:
    drop = DROP_COLUMNS.get(table, set())
    for r in records:
        r["tenant_id"] = TENANT_ID
        if table in SUCURSAL_TABLES and SUCURSAL_ID:
            r["sucursal_id"] = SUCURSAL_ID
        for col in drop:
            r.pop(col, None)
    return records


# --- Sincronizacion ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry = not args.apply

    if not AUTONOMA_SUPABASE_URL or not AUTONOMA_SUPABASE_KEY or not TENANT_ID:
        print("ERROR: Faltan variables AUTONOMA_* en .env")
        sys.exit(1)

    print(f"Modo: {'DRY-RUN' if dry else 'APPLY'}")
    print(f"Tenant: {TENANT_ID}  |  Offset: {OFFSET}")

    miranda = miranda_client()

    # Ultima comanda en Autonoma.
    last = autonoma_get("comandas", {
        "select": "id,folio,created_at",
        "tenant_id": f"eq.{TENANT_ID}",
        "order": "created_at.desc",
        "limit": "1",
    })
    if not last:
        print("ERROR: No hay comandas en Autonoma. Corre migrate-tenant.sh primero.")
        sys.exit(1)

    since = last[0]["created_at"]
    since_date = since[:10]
    print(f"Ultima comanda Autonoma: folio {last[0]['folio']}, {since}")
    print()

    # 1. Comandas
    nuevas = miranda_fetch(miranda, "comandas", gt_field="created_at", gt_value=since)
    print(f"  comandas:       {len(nuevas)} nuevas")
    comanda_ids = [c["id"] for c in nuevas]
    if not dry and nuevas:
        for c in nuevas:
            c["tenant_id"] = TENANT_ID
            c["client_sale_id"] = c["id"]
            if SUCURSAL_ID:
                c["sucursal_id"] = SUCURSAL_ID
        autonoma_insert("comandas", nuevas)

    # 2. Comanda items
    items = miranda_fetch_by_ids(miranda, "comanda_items", "comanda_id", comanda_ids) if comanda_ids else []
    print(f"  comanda_items:  {len(items)}")
    if not dry and items:
        inject(items, "comanda_items")
        for it in items:
            it.pop("id", None)
            if OFFSET and "producto_id" in it:
                try:
                    it["producto_id"] = int(it["producto_id"]) + OFFSET
                except (TypeError, ValueError):
                    pass
        autonoma_insert("comanda_items", items)

    # 3. Comanda pagos
    pagos = miranda_fetch_by_ids(miranda, "comanda_pagos", "comanda_id", comanda_ids) if comanda_ids else []
    print(f"  comanda_pagos:  {len(pagos)}")
    if not dry and pagos:
        autonoma_insert("comanda_pagos", inject(pagos, "comanda_pagos"))

    # 4. Gastos
    gastos = miranda_fetch(miranda, "gastos", gt_field="created_at", gt_value=since)
    print(f"  gastos:         {len(gastos)}")
    if not dry and gastos:
        autonoma_insert("gastos", inject(gastos, "gastos"))

    # 5. Propinas
    propinas = miranda_fetch(miranda, "propinas", order="fecha", gt_field="fecha", gt_value=since)
    print(f"  propinas:       {len(propinas)}")
    if not dry and propinas:
        autonoma_insert("propinas", inject(propinas, "propinas"))

    # 6. Cierres
    cierres = miranda_fetch(miranda, "cierres_caja", order="fecha", gt_field="fecha", gt_value=since_date)
    print(f"  cierres_caja:   {len(cierres)}")
    if not dry and cierres:
        autonoma_insert("cierres_caja", inject(cierres, "cierres_caja"))

    # Verificacion
    print()
    print("=== Verificacion ===")
    for table in ["comandas", "comanda_pagos", "gastos", "propinas", "cierres_caja"]:
        m = miranda_count(miranda, table)
        a = autonoma_count(table)
        diff = m - a
        status = "OK" if diff == 0 else f"FALTAN {diff}"
        print(f"  {table:20s} Miranda={m:6d}  Autonoma={a:6d}  {status}")

    print()
    print("DRY-RUN completado. Usa --apply para ejecutar." if dry else "Sincronizacion completada.")


if __name__ == "__main__":
    main()
