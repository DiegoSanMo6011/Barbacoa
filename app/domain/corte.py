def _round2(value: float) -> float:
    return round(float(value), 2)


def calc_ventas_por_metodo(rows: list[dict]) -> dict:
    resumen = {"EFECTIVO": 0.0, "TARJETA": 0.0, "TRANSFER": 0.0, "total": 0.0}
    for r in rows:
        total = float(r.get("total") or 0)
        metodo = r.get("metodo_pago") or ""
        if metodo in resumen:
            resumen[metodo] += total
        resumen["total"] += total

    for k in ("EFECTIVO", "TARJETA", "TRANSFER", "total"):
        resumen[k] = _round2(resumen[k])
    return resumen


def calc_efectivo_teorico(ventas_efectivo: float, gastos_total: float, propinas_total: float) -> float:
    return _round2(float(ventas_efectivo) - float(gastos_total) - float(propinas_total))


def calc_diferencia(efectivo_reportado: float, efectivo_teorico: float) -> float:
    return _round2(float(efectivo_reportado) - float(efectivo_teorico))
