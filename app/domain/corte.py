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


def calc_efectivo_teorico(
    ventas_efectivo: float,
    gastos_total: float,
    propinas_tarjeta_total: float,
    propinas_efectivo_total: float = 0.0,
    caja_chica_inicial: float = 0.0,
) -> float:
    # Efectivo esperado en caja:
    #   caja_chica + ventas_efectivo + propinas_efectivo - gastos
    # - Las propinas en EFECTIVO suman: el cliente las deja en caja junto
    #   con su pago, así que deben estar físicamente en el cajón.
    # - Las propinas de TARJETA no afectan este cálculo (se cobran por terminal).
    # - Los gastos restan porque salen de la caja durante el día.
    return _round2(
        float(caja_chica_inicial)
        + float(ventas_efectivo)
        + float(propinas_efectivo_total)
        - float(gastos_total)
    )


def calc_diferencia(efectivo_reportado: float, efectivo_teorico: float) -> float:
    return _round2(float(efectivo_reportado) - float(efectivo_teorico))
