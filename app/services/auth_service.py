from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re

import bcrypt

from domain.auth import Permission, Role
from .supabase_service import SupabaseService


_PIN_RE = re.compile(r"^\d{4,6}$")


@dataclass(slots=True)
class UnlockResult:
    success: bool
    role: Role
    source: str
    message: str


class AuthService:
    """Control de acceso por rol para el POS.

    - Arranca siempre en MESERO.
    - Eleva a GERENTE/DUEÑO con PIN.
    - Si falla la red, intenta validacion local con cache temporal.
    """

    def __init__(self, db: SupabaseService):
        self.db = db
        self._current_role = Role.MESERO

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self._cache_path = os.path.join(data_dir, "auth_cache.json")

        raw_ttl = os.getenv("BARBACOA_AUTH_CACHE_TTL_HOURS", "24").strip()
        try:
            parsed_ttl = int(raw_ttl)
        except ValueError:
            parsed_ttl = 24
        self._cache_ttl_hours = max(1, parsed_ttl)

        self._permission_map: dict[Role, set[Permission]] = {
            Role.MESERO: {
                Permission.COMANDAS,
            },
            Role.GERENTE: {
                Permission.COMANDAS,
                Permission.GASTOS,
                Permission.PROPINAS,
                Permission.CORTE,
            },
            Role.DUENIO: {
                Permission.COMANDAS,
                Permission.GASTOS,
                Permission.PROPINAS,
                Permission.CORTE,
                Permission.REPORTES,
                Permission.PERSONAL,
                Permission.PRODUCTOS,
                Permission.USUARIOS,
            },
        }

    def current_role(self) -> Role:
        return self._current_role

    def lock(self) -> None:
        self._current_role = Role.MESERO

    def can(self, permission: Permission | str) -> bool:
        perm = Permission(permission) if isinstance(permission, str) else permission
        allowed = self._permission_map.get(self._current_role, set())
        return perm in allowed

    def invalidate_role_cache(self, role: Role | str) -> None:
        role_obj = Role.from_raw(role)
        data = self._load_cache()
        roles = data.get("roles") or {}
        if role_obj.value in roles:
            roles.pop(role_obj.value, None)
            data["roles"] = roles
            self._save_cache(data)

    def unlock(self, role: Role | str, pin: str) -> UnlockResult:
        role_obj = Role.from_raw(role)
        pin = (pin or "").strip()

        if role_obj == Role.MESERO:
            return UnlockResult(False, role_obj, "none", "MESERO no requiere desbloqueo")

        if not _PIN_RE.fullmatch(pin):
            return UnlockResult(False, role_obj, "none", "PIN invalido. Debe tener 4-6 digitos.")

        try:
            user = self.db.get_user_by_role(role_obj.value)
        except Exception:
            return self._unlock_offline(role_obj, pin)

        if not user:
            return UnlockResult(False, role_obj, "online", f"No existe usuario para rol {role_obj.label}")

        if not bool(user.get("activo", True)):
            return UnlockResult(False, role_obj, "online", f"Rol {role_obj.label} desactivado")

        hash_value = str(user.get("password_hash") or "")
        if not self._verify_pin(pin, hash_value):
            return UnlockResult(False, role_obj, "online", "PIN incorrecto")

        self._current_role = role_obj
        self._cache_online_success(role_obj, hash_value, active=True)
        return UnlockResult(True, role_obj, "online", f"Sesion elevada a {role_obj.label}")

    def _unlock_offline(self, role: Role, pin: str) -> UnlockResult:
        data = self._load_cache()
        roles = data.get("roles") or {}
        entry = roles.get(role.value)
        if not entry:
            return UnlockResult(
                False,
                role,
                "offline",
                "Sin cache local para este rol. Requiere validacion online.",
            )

        if not bool(entry.get("activo", True)):
            return UnlockResult(False, role, "offline", f"Rol {role.label} desactivado en cache")

        cached_at = self._parse_iso(entry.get("cached_at"))
        if not cached_at:
            return UnlockResult(False, role, "offline", "Cache local invalido")

        expires_at = cached_at + timedelta(hours=self._cache_ttl_hours)
        now = datetime.now(timezone.utc)
        if expires_at < now:
            return UnlockResult(False, role, "offline", "Cache local expirado. Requiere validacion online.")

        hash_value = str(entry.get("password_hash") or "")
        if not self._verify_pin(pin, hash_value):
            return UnlockResult(False, role, "offline", "PIN incorrecto")

        self._current_role = role
        return UnlockResult(True, role, "offline", f"Sesion elevada a {role.label} (cache local)")

    def _cache_online_success(self, role: Role, password_hash: str, active: bool) -> None:
        data = self._load_cache()
        roles = data.get("roles") or {}
        roles[role.value] = {
            "password_hash": password_hash,
            "activo": bool(active),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        data["roles"] = roles
        self._save_cache(data)

    def _load_cache(self) -> dict:
        if not os.path.exists(self._cache_path):
            return {"version": 1, "roles": {}}
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("roles", {})
                return data
        except Exception:
            pass
        return {"version": 1, "roles": {}}

    def _save_cache(self, data: dict) -> None:
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _verify_pin(pin: str, password_hash: str) -> bool:
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(pin.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def _parse_iso(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
