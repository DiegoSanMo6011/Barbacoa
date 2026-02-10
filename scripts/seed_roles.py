#!/usr/bin/env python3
from __future__ import annotations

import os
import re

import bcrypt
from dotenv import load_dotenv
from supabase import create_client


PIN_RE = re.compile(r"^\d{4,6}$")


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Falta {name} en .env")
    return value


def _validate_pin(name: str, pin: str) -> None:
    if not PIN_RE.fullmatch(pin):
        raise RuntimeError(f"{name} debe tener 4 a 6 digitos")


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _migrate_admin_to_duenio(client) -> int:
    admin_rows = (
        client.table("usuarios")
        .select("id, nombre, usuario, password_hash, activo, updated_at")
        .eq("rol", "ADMIN")
        .execute()
        .data
        or []
    )
    if not admin_rows:
        return 0

    duenio_rows = (
        client.table("usuarios")
        .select("id")
        .eq("rol", "DUENIO")
        .execute()
        .data
        or []
    )

    latest_admin = admin_rows[0]
    if duenio_rows:
        duenio_id = duenio_rows[0].get("id")
        if duenio_id:
            client.table("usuarios").update(
                {
                    "nombre": latest_admin.get("nombre") or "Dueño",
                    "usuario": latest_admin.get("usuario") or "DUENIO",
                    "password_hash": latest_admin.get("password_hash") or "",
                    "activo": bool(latest_admin.get("activo", True)),
                }
            ).eq("id", duenio_id).execute()
        for row in admin_rows:
            rid = row.get("id")
            if rid:
                client.table("usuarios").delete().eq("id", rid).execute()
        return len(admin_rows)

    primary_admin_id = latest_admin.get("id")
    if primary_admin_id:
        client.table("usuarios").update({"rol": "DUENIO"}).eq("id", primary_admin_id).execute()
    for row in admin_rows[1:]:
        rid = row.get("id")
        if rid:
            client.table("usuarios").delete().eq("id", rid).execute()
    return len(admin_rows)


def _upsert_role(client, role: str, pin: str, nombre: str, usuario: str, activo: bool = True) -> dict:
    password_hash = _hash_pin(pin)
    rows = (
        client.table("usuarios")
        .select("id, rol")
        .eq("rol", role)
        .limit(1)
        .execute()
        .data
        or []
    )

    payload = {
        "nombre": nombre,
        "usuario": usuario,
        "password_hash": password_hash,
        "rol": role,
        "activo": bool(activo),
    }

    if rows:
        rid = rows[0]["id"]
        data = client.table("usuarios").update(payload).eq("id", rid).execute().data or []
        return data[0] if data else {"id": rid, "rol": role, "updated": True}

    data = client.table("usuarios").insert(payload).execute().data or []
    return data[0] if data else {"rol": role, "created": True}


def main() -> None:
    load_dotenv()

    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_KEY")
    gerente_pin = _require_env("BARBACOA_GERENTE_PIN")
    duenio_pin = _require_env("BARBACOA_DUENIO_PIN")

    _validate_pin("BARBACOA_GERENTE_PIN", gerente_pin)
    _validate_pin("BARBACOA_DUENIO_PIN", duenio_pin)

    client = create_client(supabase_url, supabase_key)

    migrated = _migrate_admin_to_duenio(client)
    gerente = _upsert_role(
        client,
        role="GERENTE",
        pin=gerente_pin,
        nombre="Gerente",
        usuario="GERENTE",
        activo=True,
    )
    duenio = _upsert_role(
        client,
        role="DUENIO",
        pin=duenio_pin,
        nombre="Dueño",
        usuario="DUENIO",
        activo=True,
    )

    print(f"ADMIN migrados a DUEÑO (rol interno DUENIO): {migrated}")
    print(f"GERENTE listo: {gerente}")
    print(f"DUEÑO listo (rol interno DUENIO): {duenio}")


if __name__ == "__main__":
    main()
