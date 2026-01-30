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


def resumen_ventas_por_metodo(fecha: date, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)

    rows = (
        db.client.table("comandas")
        .select("total, metodo_pago")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .execute()
    ).data or []

    resumen = {"EFECTIVO": 0.0, "TARJETA": 0.0, "TRANSFER": 0.0, "total": 0.0}
    for r in rows:
        total = float(r.get("total") or 0)
        metodo = r.get("metodo_pago") or ""
        if metodo in resumen:
            resumen[metodo] += total
        resumen["total"] += total

    for k in ("EFECTIVO", "TARJETA", "TRANSFER", "total"):
        resumen[k] = round(float(resumen[k]), 2)
    return resumen


def top_productos(fecha: date, limit: int = 10, db: SupabaseService | None = None) -> list[dict]:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)

    comandas = (
        db.client.table("comandas")
        .select("id")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .execute()
    ).data or []

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

    rows = (
        db.client.table("comandas")
        .select("created_at, total")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .order("created_at")
        .execute()
    ).data or []

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
