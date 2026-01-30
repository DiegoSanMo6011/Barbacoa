from __future__ import annotations

from datetime import date

from domain.corte import calc_ventas_por_metodo
from .supabase_service import SupabaseService


def _get_db(db: SupabaseService | None) -> SupabaseService:
    return db or SupabaseService()


def get_ventas_por_metodo(fecha: date, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)
    rows = (
        db.client.table("comandas")
        .select("total, metodo_pago")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .execute()
    ).data or []
    return calc_ventas_por_metodo(rows)


def get_gastos_total(fecha: date, db: SupabaseService | None = None) -> float:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)
    rows = (
        db.client.table("gastos")
        .select("monto")
        .gte("created_at", desde)
        .lte("created_at", hasta)
        .execute()
    ).data or []
    return round(sum(float(r.get("monto") or 0) for r in rows), 2)


def get_propinas_total(fecha: date, db: SupabaseService | None = None) -> float:
    db = _get_db(db)
    desde, hasta = db._day_range(fecha)
    rows = (
        db.client.table("propinas")
        .select("monto")
        .gte("fecha", desde)
        .lte("fecha", hasta)
        .execute()
    ).data or []
    return round(sum(float(r.get("monto") or 0) for r in rows), 2)


def get_corte_por_fecha(fecha: date, db: SupabaseService | None = None) -> dict | None:
    db = _get_db(db)
    res = db.client.table("cierres_caja").select("*").eq("fecha", fecha.isoformat()).execute()
    if not res.data:
        return None
    return res.data[0]


def save_corte(payload: dict, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    fecha = payload.get("fecha")
    if not fecha:
        raise ValueError("fecha es obligatoria para guardar el corte")

    data = {
        "fecha": fecha,
        "total_ventas": round(float(payload.get("total_ventas") or 0), 2),
        "total_gastos": round(float(payload.get("total_gastos") or 0), 2),
        "neto": round(float(payload.get("neto") or 0), 2),
        "efectivo_reportado": round(float(payload.get("efectivo_reportado") or 0), 2),
        "diferencia_efectivo": round(float(payload.get("diferencia_efectivo") or 0), 2),
        "notas": payload.get("notas"),
    }

    existente = get_corte_por_fecha(date.fromisoformat(fecha), db=db)
    if existente:
        res = db.client.table("cierres_caja").update(data).eq("id", existente["id"]).execute()
        return res.data[0]

    res = db.client.table("cierres_caja").insert(data).execute()
    return res.data[0]
