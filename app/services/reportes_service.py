from __future__ import annotations

from datetime import date, datetime
import re

from .supabase_service import SupabaseService


def _get_db(db: SupabaseService | None) -> SupabaseService:
    return db or SupabaseService()


def _parse_iso(dt_str: str) -> datetime:
    if not dt_str:
        raise ValueError("timestamp vacío")
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    # Normaliza offsets con espacio: "2026-01-24T03:40:22.59891+0 0:00"
    dt_str = re.sub(r"([+-])0\s+0:00$", r"\g<1>00:00", dt_str)
    # Normaliza offsets tipo "+0000" o "+00 00"
    dt_str = re.sub(r"([+-]\d{2})\s?(\d{2})$", r"\1:\2", dt_str)
    return datetime.fromisoformat(dt_str)


def _extract_date_key(dt_str: str) -> str | None:
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    # Usa la parte YYYY-MM-DD aunque el offset venga malformado
    if "T" in dt_str:
        return dt_str.split("T", 1)[0]
    if len(dt_str) >= 10:
        return dt_str[:10]
    return None


def _range_iso(db: SupabaseService, fecha_inicio: date, fecha_fin: date) -> tuple[str, str]:
    if fecha_fin < fecha_inicio:
        raise ValueError("fecha_fin debe ser >= fecha_inicio")
    desde, _ = db._day_range(fecha_inicio)
    _, hasta = db._day_range(fecha_fin)
    return desde, hasta


def get_top_productos(
    fecha_inicio: date,
    fecha_fin: date,
    limit: int = 10,
    db: SupabaseService | None = None,
) -> list[dict]:
    db = _get_db(db)
    desde, hasta = _range_iso(db, fecha_inicio, fecha_fin)

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
            agg[nombre] = {"producto": nombre, "cantidad_total": 0, "subtotal_total": 0.0}
        agg[nombre]["cantidad_total"] += int(it.get("cantidad") or 0)
        agg[nombre]["subtotal_total"] += float(it.get("subtotal") or 0)

    result = list(agg.values())
    result.sort(key=lambda x: (-x["subtotal_total"], x["producto"]))
    if limit is not None and limit > 0:
        result = result[:limit]
    for r in result:
        r["subtotal_total"] = round(float(r["subtotal_total"]), 2)
    return result


def get_ventas_por_dia(
    fecha_inicio: date,
    fecha_fin: date,
    db: SupabaseService | None = None,
) -> list[dict]:
    db = _get_db(db)
    desde, hasta = _range_iso(db, fecha_inicio, fecha_fin)

    rows = (
        db.client.table("comandas")
        .select("created_at, total")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .order("created_at")
        .execute()
    ).data or []

    agg: dict[str, float] = {}
    for r in rows:
        created_at = r.get("created_at")
        key = _extract_date_key(created_at)
        if not key:
            continue
        agg[key] = agg.get(key, 0.0) + float(r.get("total") or 0)

    result = [{"fecha": k, "total": round(v, 2)} for k, v in agg.items()]
    result.sort(key=lambda x: x["fecha"])
    return result


def get_ventas_por_metodo(
    fecha_inicio: date,
    fecha_fin: date,
    db: SupabaseService | None = None,
) -> dict:
    db = _get_db(db)
    desde, hasta = _range_iso(db, fecha_inicio, fecha_fin)

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
