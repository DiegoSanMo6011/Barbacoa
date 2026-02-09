from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    MESERO = "MESERO"
    GERENTE = "GERENTE"
    DUENIO = "DUENIO"

    @classmethod
    def from_raw(cls, value: str | "Role") -> "Role":
        if isinstance(value, Role):
            return value
        normalized = (value or "").strip().upper()
        if normalized == "ADMIN":
            normalized = "DUENIO"
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"rol invalido: {value}") from exc


class Permission(str, Enum):
    COMANDAS = "COMANDAS"
    GASTOS = "GASTOS"
    PROPINAS = "PROPINAS"
    CORTE = "CORTE"
    REPORTES = "REPORTES"
    PERSONAL = "PERSONAL"
    PRODUCTOS = "PRODUCTOS"
    USUARIOS = "USUARIOS"
