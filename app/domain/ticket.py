from __future__ import annotations

from datetime import datetime


def _line(char: str = "-", n: int = 32) -> str:
    return char * n


def build_ticket_text(payload: dict) -> str:
    negocio = payload.get("negocio", "BARBACOA DE MIRAND")
    folio = payload.get("folio", "N/A")
    fecha_hora = payload.get("fecha_hora", datetime.now())
    mesa = payload.get("mesa", "") or "-"
    mesero = payload.get("mesero", "") or "-"
    metodo = payload.get("metodo_pago", "") or "-"
    propina = float(payload.get("propina") or 0)
    total = float(payload.get("total") or 0)
    items = payload.get("items", [])

    if isinstance(fecha_hora, datetime):
        fecha_txt = fecha_hora.strftime("%Y-%m-%d %H:%M")
    else:
        fecha_txt = str(fecha_hora)

    lines = []
    lines.append(negocio.upper())
    lines.append(_line("="))
    lines.append(f"Folio: {folio}")
    lines.append(f"Fecha: {fecha_txt}")
    lines.append(f"Mesa: {mesa}")
    lines.append(f"Mesero: {mesero}")
    lines.append(_line())
    lines.append("Cant  Producto           Subt")
    lines.append(_line())

    for it in items:
        nombre = str(it.get("nombre_snapshot") or "Producto")
        qty = int(it.get("cantidad") or 0)
        subtotal = float(it.get("subtotal") or 0)
        nombre_short = (nombre[:16] + "..") if len(nombre) > 18 else nombre
        lines.append(f"{qty:<5} {nombre_short:<18} ${subtotal:>6.2f}")

    lines.append(_line())
    lines.append(f"Metodo: {metodo}")
    lines.append(f"Propina: ${propina:.2f}")
    lines.append(f"TOTAL:   ${total:.2f}")
    lines.append(_line("="))
    lines.append("Gracias por su compra")
    return "\n".join(lines)
