from __future__ import annotations

from datetime import date, datetime
import re
from typing import Iterable

from .supabase_service import SupabaseService


def _get_db(db: SupabaseService | None) -> SupabaseService:
    return db or SupabaseService()


def _parse_iso(dt_str: str) -> datetime:
    # Supabase puede devolver timestamps con sufijo Z
    if not dt_str:
        raise ValueError("timestamp vacío")
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    dt_str = re.sub(r"([+-])0\s+0:00$", r"\g<1>00:00", dt_str)
    dt_str = re.sub(r"([+-]\d{2})\s?(\d{2})$", r"\1:\2", dt_str)
    return datetime.fromisoformat(dt_str)


def _active_comandas_rows(db: SupabaseService, *, desde: str, hasta: str, columns: str) -> list[dict]:
    def _columns_without_status(raw: str) -> str:
        parts = [p.strip() for p in str(raw or "").split(",") if p.strip()]
        filtered = [p for p in parts if p.lower() != "status"]
        return ", ".join(filtered) or "id"

    query = db.client.table("comandas").select(columns).gte("created_at", desde).lte("created_at", hasta)
    try:
        rows = query.neq("status", "CANCELADA").execute().data or []
    except Exception as exc:
        try:
            rows = query.execute().data or []
        except Exception as inner_exc:
            msg = str(inner_exc).lower()
            if "status" in msg and ("column" in msg or "schema cache" in msg):
                rows = (
                    db.client.table("comandas")
                    .select(_columns_without_status(columns))
                    .gte("created_at", desde)
                    .lte("created_at", hasta)
                    .execute()
                ).data or []
            else:
                raise inner_exc from exc
    return [r for r in rows if str(r.get("status") or "").upper() != "CANCELADA"]


def resumen_ventas_por_metodo(fecha: date, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    return db.resumen_ventas_por_metodo_dia(fecha)


def top_productos(fecha: date, limit: int = 10, db: SupabaseService | None = None) -> list[dict]:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)

    comandas = _active_comandas_rows(db, desde=desde, hasta=hasta, columns="id, status")

    comanda_ids = [c["id"] for c in comandas]
    if not comanda_ids:
        return []

    items = (
        db.client.table("comanda_items")
        .select("nombre_snapshot, cantidad, subtotal, comanda_id")
        .in_("comanda_id", comanda_ids)
        .execute()
    ).data or []

    agg: dict[str, dict] = {}
    for it in items:
        nombre = it.get("nombre_snapshot") or "SIN_NOMBRE"
        if nombre not in agg:
            agg[nombre] = {
                "producto": nombre,
                "cantidad_total": 0,
                "subtotal_total": 0.0,
            }
        agg[nombre]["cantidad_total"] += int(it.get("cantidad") or 0)
        agg[nombre]["subtotal_total"] += float(it.get("subtotal") or 0)

    result = list(agg.values())
    result.sort(key=lambda x: (-x["subtotal_total"], x["producto"]))
    if limit is not None and limit > 0:
        result = result[:limit]
    for r in result:
        r["subtotal_total"] = round(float(r["subtotal_total"]), 2)
    return result


def ventas_por_hora(fecha: date, db: SupabaseService | None = None) -> list[dict]:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)

    rows = _active_comandas_rows(db, desde=desde, hasta=hasta, columns="created_at, total, status")
    rows.sort(key=lambda x: str(x.get("created_at") or ""))

    # Inicializa 24 horas
    horas = [{"hora": h, "total": 0.0, "num_comandas": 0} for h in range(24)]
    for r in rows:
        created_at = r.get("created_at")
        if not created_at:
            continue
        dt = _parse_iso(created_at)
        h = dt.hour
        horas[h]["total"] += float(r.get("total") or 0)
        horas[h]["num_comandas"] += 1

    for h in horas:
        h["total"] = round(float(h["total"]), 2)
    return horas


def demo_reportes(fecha: date | None = None) -> None:
    fecha = fecha or date.today()
    db = SupabaseService()

    print(f"== Reportes para {fecha.isoformat()} ==")
    print("Resumen por metodo:", resumen_ventas_por_metodo(fecha, db=db))
    print("Top productos:", top_productos(fecha, limit=10, db=db))
    print("Ventas por hora:", ventas_por_hora(fecha, db=db))
