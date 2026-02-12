from __future__ import annotations

from datetime import datetime
from textwrap import wrap


TICKET_WIDTH = 32


def _line(char: str = "-", n: int = TICKET_WIDTH) -> str:
    return char * n


def _extend_wrapped(lines: list[str], text: str, width: int = TICKET_WIDTH) -> None:
    wrapped = wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if not wrapped:
        lines.append("")
        return
    lines.extend(wrapped)


def build_ticket_text(payload: dict) -> str:
    negocio = payload.get("negocio", "Barbacoa de Miranda")
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
    lines.append(_line())
    lines.append("FACTURACION")
    lines.append(_line())
    _extend_wrapped(lines, "Para facturar requerimos que nos mande la foto de este ticket.")
    lines.append("")
    _extend_wrapped(lines, "Datos necesarios para el envio de su factura:")
    lines.append("Nombre\n")
    lines.append("RFC\n")
    lines.append("CP\n")
    lines.append("REGIMEN FISCAL\n")
    lines.append("CORREO ELECTRONICO\n")
    lines.append("")
    _extend_wrapped(lines, "Mandar los datos al WhatsApp 4423536786")
    lines.append(_line("="))
    lines.append("Gracias por su compra")
    return "\n".join(lines)
