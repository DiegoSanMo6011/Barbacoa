from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import json
import os
import re
import secrets
import smtplib
import ssl

import bcrypt

from domain.auth import Permission, Role
from .supabase_service import SupabaseService


_PIN_RE = re.compile(r"^\d{4,6}$")
_DEFAULT_RECOVERY_EMAIL_TO = "sistemamirandapos@gmail.com"


@dataclass(slots=True)
class UnlockResult:
    success: bool
    role: Role
    source: str
    message: str


@dataclass(slots=True)
class RecoverPinResult:
    success: bool
    role: Role
    message: str


@dataclass(slots=True)
class RequestRecoveryCodeResult:
    success: bool
    role: Role
    destination: str
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
        self._recovery_path = os.path.join(data_dir, "recovery_codes.json")

        self._recovery_email_to = (os.getenv("BARBACOA_RECOVERY_EMAIL_TO") or _DEFAULT_RECOVERY_EMAIL_TO).strip()
        self._smtp_host = (os.getenv("BARBACOA_SMTP_HOST") or "smtp.gmail.com").strip()
        raw_smtp_port = (os.getenv("BARBACOA_SMTP_PORT") or "587").strip()
        try:
            self._smtp_port = int(raw_smtp_port)
        except ValueError:
            self._smtp_port = 587
        self._smtp_user = (os.getenv("BARBACOA_SMTP_USER") or "").strip()
        self._smtp_password = (os.getenv("BARBACOA_SMTP_PASSWORD") or "").strip()
        self._smtp_from = (os.getenv("BARBACOA_SMTP_FROM") or self._smtp_user or self._recovery_email_to).strip()

        raw_use_ssl = (os.getenv("BARBACOA_SMTP_USE_SSL") or "").strip().lower()
        self._smtp_use_ssl = raw_use_ssl in {"1", "true", "yes", "on", "si", "sí"}
        raw_starttls = (os.getenv("BARBACOA_SMTP_USE_STARTTLS") or "").strip().lower()
        if raw_starttls:
            self._smtp_use_starttls = raw_starttls in {"1", "true", "yes", "on", "si", "sí"}
        else:
            self._smtp_use_starttls = not self._smtp_use_ssl

        raw_ttl_minutes = (os.getenv("BARBACOA_RECOVERY_CODE_TTL_MINUTES") or "10").strip()
        try:
            ttl_minutes = int(raw_ttl_minutes)
        except ValueError:
            ttl_minutes = 10
        self._recovery_ttl_minutes = max(2, min(30, ttl_minutes))

        raw_code_len = (os.getenv("BARBACOA_RECOVERY_CODE_LENGTH") or "6").strip()
        try:
            code_len = int(raw_code_len)
        except ValueError:
            code_len = 6
        self._recovery_code_len = max(6, min(8, code_len))

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

    def has_recovery_channel(self, role: Role | str) -> bool:
        role_obj = Role.from_raw(role)
        if role_obj == Role.MESERO:
            return False
        return not self._missing_recovery_config()

    def recovery_destination(self) -> str:
        return self._recovery_email_to

    def request_recovery_code(self, role: Role | str) -> RequestRecoveryCodeResult:
        role_obj = Role.from_raw(role)
        destination = self.recovery_destination()

        if role_obj == Role.MESERO:
            return RequestRecoveryCodeResult(
                False,
                role_obj,
                destination,
                "MESERO no usa PIN administrativo.",
            )

        if not self.has_recovery_channel(role_obj):
            missing = ", ".join(self._missing_recovery_config())
            return RequestRecoveryCodeResult(
                False,
                role_obj,
                destination,
                f"Falta configurar en .env: {missing}.",
            )

        code = self._generate_recovery_code()
        try:
            self._send_recovery_email(role_obj, code)
        except Exception as exc:
            return RequestRecoveryCodeResult(
                False,
                role_obj,
                destination,
                f"No se pudo enviar el codigo por correo: {exc}",
            )

        self._store_recovery_code(role_obj, code)
        return RequestRecoveryCodeResult(
            True,
            role_obj,
            destination,
            f"Codigo enviado a {destination}. Expira en {self._recovery_ttl_minutes} minutos.",
        )

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

    def recover_pin(self, role: Role | str, recovery_code: str, new_pin: str) -> RecoverPinResult:
        role_obj = Role.from_raw(role)
        recovery_code = (recovery_code or "").strip()
        new_pin = (new_pin or "").strip()

        if role_obj == Role.MESERO:
            return RecoverPinResult(False, role_obj, "MESERO no usa PIN administrativo.")

        if not _PIN_RE.fullmatch(new_pin):
            return RecoverPinResult(False, role_obj, "PIN invalido. Debe tener 4-6 digitos.")

        if not recovery_code:
            return RecoverPinResult(False, role_obj, "Captura el codigo de recuperacion.")

        entry = self._get_recovery_entry(role_obj)
        if not entry:
            return RecoverPinResult(
                False,
                role_obj,
                "No hay codigo vigente. Solicita uno nuevo desde 'Olvide mi PIN'.",
            )

        expires_at = self._parse_iso(entry.get("expires_at"))
        if not expires_at or expires_at < datetime.now(timezone.utc):
            self._clear_recovery_entry(role_obj)
            return RecoverPinResult(False, role_obj, "El codigo expiro. Solicita uno nuevo.")

        code_hash = str(entry.get("code_hash") or "")
        if not self._verify_pin(recovery_code, code_hash):
            return RecoverPinResult(False, role_obj, "Codigo de recuperacion incorrecto.")

        password_hash = bcrypt.hashpw(new_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            user = self.db.set_role_pin(role_obj.value, password_hash)
        except Exception:
            return RecoverPinResult(False, role_obj, "No se pudo restablecer PIN. Verifica conexion a Supabase.")

        self._clear_recovery_entry(role_obj)
        self.invalidate_role_cache(role_obj)
        active = bool((user or {}).get("activo", True))
        if active:
            self._current_role = role_obj
            self._cache_online_success(role_obj, password_hash, active=True)
            return RecoverPinResult(True, role_obj, f"PIN restablecido para {role_obj.label}.")

        self._current_role = Role.MESERO
        self._cache_online_success(role_obj, password_hash, active=False)
        return RecoverPinResult(
            True,
            role_obj,
            f"PIN restablecido, pero el perfil {role_obj.label} esta desactivado.",
        )

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

    def _generate_recovery_code(self) -> str:
        n = 10**self._recovery_code_len
        return f"{secrets.randbelow(n):0{self._recovery_code_len}d}"

    def _store_recovery_code(self, role: Role, code: str) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self._recovery_ttl_minutes)
        code_hash = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        data = self._load_recovery_state()
        roles = data.get("roles") or {}
        roles[role.value] = {
            "code_hash": code_hash,
            "requested_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "destination": self._recovery_email_to,
        }
        data["roles"] = roles
        self._save_recovery_state(data)

    def _get_recovery_entry(self, role: Role) -> dict | None:
        data = self._load_recovery_state()
        roles = data.get("roles") or {}
        entry = roles.get(role.value)
        return entry if isinstance(entry, dict) else None

    def _clear_recovery_entry(self, role: Role) -> None:
        data = self._load_recovery_state()
        roles = data.get("roles") or {}
        if role.value in roles:
            roles.pop(role.value, None)
            data["roles"] = roles
            self._save_recovery_state(data)

    def _load_recovery_state(self) -> dict:
        if not os.path.exists(self._recovery_path):
            return {"version": 1, "roles": {}}
        try:
            with open(self._recovery_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("roles", {})
                return data
        except Exception:
            pass
        return {"version": 1, "roles": {}}

    def _save_recovery_state(self, data: dict) -> None:
        with open(self._recovery_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _send_recovery_email(self, role: Role, code: str) -> None:
        destination = self._recovery_email_to
        if not destination:
            raise RuntimeError("BARBACOA_RECOVERY_EMAIL_TO vacio")

        subject = f"[Barbacoa POS] Codigo de recuperacion {role.label}"
        body = (
            f"Se solicito recuperar el PIN del rol {role.label}.\n\n"
            f"Codigo: {code}\n"
            f"Vigencia: {self._recovery_ttl_minutes} minutos\n\n"
            "Si no solicitaste este cambio, ignora este correo."
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._smtp_from
        msg["To"] = destination
        msg.set_content(body)

        timeout_seconds = 20
        if self._smtp_use_ssl:
            with smtplib.SMTP_SSL(self._smtp_host, self._smtp_port, timeout=timeout_seconds) as server:
                if self._smtp_user:
                    server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)
            return

        with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=timeout_seconds) as server:
            if self._smtp_use_starttls:
                context = ssl.create_default_context()
                server.starttls(context=context)
            if self._smtp_user:
                server.login(self._smtp_user, self._smtp_password)
            server.send_message(msg)

    def _missing_recovery_config(self) -> list[str]:
        missing: list[str] = []
        if not self._recovery_email_to:
            missing.append("BARBACOA_RECOVERY_EMAIL_TO")
        if not self._smtp_user:
            missing.append("BARBACOA_SMTP_USER")
        if not self._smtp_password:
            missing.append("BARBACOA_SMTP_PASSWORD")
        return missing

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
