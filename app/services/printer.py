from __future__ import annotations

import glob
import os
import shutil
import subprocess
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def should_autoprint() -> bool:
    return _env_flag("BARBACOA_PRINTER_AUTOPRINT", default=False)


def _detect_usb_device() -> str | None:
    devices = sorted(glob.glob("/dev/usb/lp*"))
    for path in devices:
        if os.path.exists(path):
            return path
    return None


def _build_payload(text: str, encoding: str, feed_lines: int, cut: bool) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    payload = b"\x1b@"  # ESC @ (init)
    payload += normalized.encode(encoding, errors="replace")
    if feed_lines > 0:
        payload += b"\n" * feed_lines
    if cut:
        payload += b"\x1dV\x01"  # GS V 1 (partial cut)
    return payload


def _print_via_device(payload: bytes, device_path: str) -> None:
    try:
        with open(device_path, "wb") as f:
            f.write(payload)
            f.flush()
    except PermissionError as exc:
        raise RuntimeError(
            f"Sin permisos para escribir en {device_path}. "
            "Agrega el usuario al grupo 'lp' o configura una regla udev."
        ) from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"No se encontró el dispositivo {device_path}.") from exc


def _print_via_cups(payload: bytes, printer_name: str | None) -> None:
    if not shutil.which("lp"):
        raise RuntimeError("No se encontró el comando 'lp'. Instala CUPS o usa BARBACOA_PRINTER_DEVICE.")
    cmd = ["lp", "-o", "raw"]
    if printer_name:
        cmd += ["-d", printer_name]
    result = subprocess.run(cmd, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Error de CUPS: {err or 'lp falló'}")


def print_ticket_text(text: str) -> None:
    device = os.getenv("BARBACOA_PRINTER_DEVICE")
    printer_name = os.getenv("BARBACOA_PRINTER_NAME")
    use_cups = _env_flag("BARBACOA_PRINTER_USE_CUPS", default=False)
    encoding = os.getenv("BARBACOA_PRINTER_ENCODING") or "cp437"
    feed_lines = _env_int("BARBACOA_PRINTER_FEED", default=4)
    cut = _env_flag("BARBACOA_PRINTER_CUT", default=True)

    payload = _build_payload(text, encoding=encoding, feed_lines=feed_lines, cut=cut)

    if use_cups or printer_name:
        _print_via_cups(payload, printer_name)
        return

    device_path = device or _detect_usb_device()
    if not device_path:
        raise RuntimeError(
            "No se encontró impresora USB. "
            "Define BARBACOA_PRINTER_DEVICE (ej. /dev/usb/lp0) o usa CUPS."
        )
    _print_via_device(payload, device_path)
