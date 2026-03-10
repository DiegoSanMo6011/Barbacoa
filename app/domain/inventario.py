"""
domain/inventario.py
Lógica pura de cálculo para el módulo de inventario.
No tiene dependencias de base de datos ni de UI.
"""
from __future__ import annotations


def calc_consumo(
    items_comanda: list[dict],
    recetas: list[dict],
) -> dict[str, float]:
    """
    Calcula cuánto se debe descontar de cada insumo dada una lista de ítems
    de comanda y las recetas de los productos involucrados.

    Args:
        items_comanda: lista de dicts con {producto_id, cantidad, ...}
        recetas: lista de dicts con {producto_id, insumo_id, cantidad}

    Returns:
        dict {insumo_id: total_a_descontar}
    """
    # Indexar cantidad vendida por producto_id
    qty_por_producto: dict = {}
    for item in items_comanda:
        pid = str(item.get("producto_id") or "")
        qty = float(item.get("cantidad") or 0)
        if pid:
            qty_por_producto[pid] = qty_por_producto.get(pid, 0.0) + qty

    # Calcular consumo total por insumo
    consumo: dict[str, float] = {}
    for receta in recetas:
        pid = str(receta.get("producto_id") or "")
        iid = str(receta.get("insumo_id") or "")
        cant_receta = float(receta.get("cantidad") or 0)
        qty_vendida = qty_por_producto.get(pid, 0.0)
        if not iid or cant_receta <= 0 or qty_vendida <= 0:
            continue
        consumo[iid] = round(consumo.get(iid, 0.0) + cant_receta * qty_vendida, 4)

    return consumo


def get_alertas_stock(insumos: list[dict]) -> list[dict]:
    """
    Retorna los insumos cuyo stock_actual está en o por debajo del stock_minimo.

    Args:
        insumos: lista de dicts con {id, nombre, unidad, stock_actual, stock_minimo, ...}

    Returns:
        Lista filtrada de insumos con alerta de stock bajo.
    """
    alertas = []
    for insumo in insumos:
        actual = float(insumo.get("stock_actual") or 0)
        minimo = float(insumo.get("stock_minimo") or 0)
        if actual <= minimo:
            alertas.append(insumo)
    return alertas


def format_stock(valor: float, unidad: str) -> str:
    """Formatea un valor de stock con su unidad para mostrar en UI."""
    if valor == int(valor):
        return f"{int(valor)} {unidad}"
    return f"{valor:.2f} {unidad}"
