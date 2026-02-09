from __future__ import annotations

from datetime import date, datetime, timezone

from domain.corte import calc_ventas_por_metodo
from .supabase_service import SupabaseService

ESTADO_ABIERTO = "ABIERTO"
ESTADO_CERRADO = "CERRADO"


def _get_db(db: SupabaseService | None) -> SupabaseService:
    return db or SupabaseService()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_estado(value: str | None) -> str:
    estado = (value or ESTADO_CERRADO).strip().upper()
    if estado not in {ESTADO_ABIERTO, ESTADO_CERRADO}:
        return ESTADO_CERRADO
    return estado


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
    row = res.data[0]
    row["estado"] = _normalize_estado(row.get("estado"))
    row["reaperturas"] = int(row.get("reaperturas") or 0)
    row["caja_chica_inicial"] = float(row.get("caja_chica_inicial") or 0)
    return row


def _is_missing_column_error(exc: Exception, column: str) -> bool:
    msg = str(exc).lower()
    return column.lower() in msg and ("column" in msg or "schema cache" in msg)


def _ensure_jornada_columns(exc: Exception) -> None:
    for col in ("estado", "abierto_at", "cerrado_at", "reaperturas", "reabierto_at", "caja_chica_inicial"):
        if _is_missing_column_error(exc, col):
            raise ValueError("Falta migración SQL: ejecuta `sql/cierres_jornada.sql` en Supabase.") from exc
    raise exc


def iniciar_jornada(fecha: date, caja_chica_inicial: float, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    caja = round(float(caja_chica_inicial or 0), 2)
    if caja < 0:
        raise ValueError("caja_chica_inicial debe ser >= 0")

    existente = get_corte_por_fecha(fecha, db=db)
    if existente:
        estado = _normalize_estado(existente.get("estado"))
        if estado == ESTADO_ABIERTO:
            raise ValueError("La jornada ya está iniciada para esta fecha.")
        raise ValueError("La jornada ya fue cerrada. Reabre para editar.")

    data = {
        "fecha": fecha.isoformat(),
        "total_ventas": 0.0,
        "total_gastos": 0.0,
        "neto": 0.0,
        "caja_chica_inicial": caja,
        "efectivo_reportado": 0.0,
        "diferencia_efectivo": 0.0,
        "estado": ESTADO_ABIERTO,
        "abierto_at": _now_iso(),
        "cerrado_at": None,
        "reaperturas": 0,
        "reabierto_at": None,
        "notas": None,
    }
    try:
        res = db.client.table("cierres_caja").insert(data).execute()
        return res.data[0]
    except Exception as exc:
        _ensure_jornada_columns(exc)


def cerrar_jornada(payload: dict, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    fecha = payload.get("fecha")
    if not fecha:
        raise ValueError("fecha es obligatoria para cerrar jornada")

    fecha_dt = date.fromisoformat(str(fecha))
    existente = get_corte_por_fecha(fecha_dt, db=db)
    if not existente:
        raise ValueError("Primero inicia la jornada antes de cerrar el día.")

    if _normalize_estado(existente.get("estado")) == ESTADO_CERRADO:
        raise ValueError("El día ya está cerrado. Reabre para editar.")

    data = {
        "total_ventas": round(float(payload.get("total_ventas") or 0), 2),
        "total_gastos": round(float(payload.get("total_gastos") or 0), 2),
        "neto": round(float(payload.get("neto") or 0), 2),
        "caja_chica_inicial": round(float(payload.get("caja_chica_inicial") or 0), 2),
        "efectivo_reportado": round(float(payload.get("efectivo_reportado") or 0), 2),
        "diferencia_efectivo": round(float(payload.get("diferencia_efectivo") or 0), 2),
        "notas": payload.get("notas"),
        "estado": ESTADO_CERRADO,
        "cerrado_at": _now_iso(),
    }

    try:
        res = db.client.table("cierres_caja").update(data).eq("id", existente["id"]).execute()
        return res.data[0]
    except Exception as exc:
        _ensure_jornada_columns(exc)


def reabrir_jornada(fecha: date, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    existente = get_corte_por_fecha(fecha, db=db)
    if not existente:
        raise ValueError("No existe jornada para esa fecha.")

    if _normalize_estado(existente.get("estado")) == ESTADO_ABIERTO:
        return existente

    reaperturas = int(existente.get("reaperturas") or 0) + 1
    data = {
        "estado": ESTADO_ABIERTO,
        "cerrado_at": None,
        "reabierto_at": _now_iso(),
        "reaperturas": reaperturas,
    }
    try:
        res = db.client.table("cierres_caja").update(data).eq("id", existente["id"]).execute()
        return res.data[0]
    except Exception as exc:
        _ensure_jornada_columns(exc)


def save_corte(payload: dict, db: SupabaseService | None = None) -> dict:
    db = _get_db(db)
    fecha = payload.get("fecha")
    if not fecha:
        raise ValueError("fecha es obligatoria para guardar el corte")
    fecha_dt = date.fromisoformat(str(fecha))
    existente = get_corte_por_fecha(fecha_dt, db=db)
    if not existente:
        iniciar_jornada(
            fecha_dt,
            caja_chica_inicial=float(payload.get("caja_chica_inicial") or 0),
            db=db,
        )
    return cerrar_jornada(payload, db=db)
