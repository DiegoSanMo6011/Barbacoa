#!/usr/bin/env python3
from __future__ import annotations

import argparse
import compileall
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SkipCheck(Exception):
    pass


@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    message: str
    duration_s: float
    details: str = ""


class Validator:
    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.results: list[CheckResult] = []

    def run(self, name: str, fn: Callable[[], str]) -> None:
        start = time.perf_counter()
        status = "OK"
        message = ""
        details = ""
        try:
            message = fn()
        except SkipCheck as exc:
            status = "SKIP"
            message = str(exc)
        except Exception as exc:
            status = "ERROR"
            message = f"{type(exc).__name__}: {exc}"
            details = traceback.format_exc()
        elapsed = time.perf_counter() - start

        self.results.append(
            CheckResult(
                name=name,
                status=status,
                message=message,
                duration_s=elapsed,
                details=details,
            )
        )

        icon = {"OK": "[OK]", "ERROR": "[ERROR]", "SKIP": "[SKIP]"}[status]
        print(f"{icon} {name}: {message} ({elapsed:.2f}s)")
        if details and self.verbose:
            print(details)

    def has_errors(self) -> bool:
        return any(r.status == "ERROR" for r in self.results)

    def print_summary(self) -> None:
        total = len(self.results)
        ok = sum(1 for r in self.results if r.status == "OK")
        errors = sum(1 for r in self.results if r.status == "ERROR")
        skip = sum(1 for r in self.results if r.status == "SKIP")
        print("")
        print(f"Resumen: total={total} ok={ok} error={errors} skip={skip}")
        if errors == 0:
            print("RESULTADO FINAL: OK")
        else:
            print("RESULTADO FINAL: ERROR")


def expect_raises(exc_type: type[BaseException], fn: Callable, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as exc:  # pragma: no cover
        raise AssertionError(
            f"Se esperaba {exc_type.__name__} y ocurrio {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"Se esperaba {exc_type.__name__} y no ocurrio.")


@contextmanager
def patched_env(values: dict[str, str]):
    previous: dict[str, str | None] = {}
    try:
        for key, value in values.items():
            previous[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def supabase_env_ready() -> bool:
    return bool((os.getenv("SUPABASE_URL") or "").strip() and (os.getenv("SUPABASE_KEY") or "").strip())


def check_python_version() -> str:
    if sys.version_info < (3, 10):
        raise AssertionError(f"Python actual {sys.version.split()[0]}, se requiere >= 3.10")
    return f"Python {sys.version.split()[0]}"


def check_required_paths() -> str:
    required = [
        "app/main.py",
        "app/services/supabase_service.py",
        "app/services/corte_service.py",
        "app/ui/corte_view.py",
        "app/domain/models.py",
        "scripts/seed_roles.py",
        "sql/schema.sql",
    ]
    missing = [path for path in required if not (ROOT_DIR / path).exists()]
    if missing:
        raise AssertionError(f"Faltan rutas clave: {missing}")
    return f"{len(required)} rutas clave encontradas"


def check_compileall() -> str:
    ok_app = compileall.compile_dir(str(ROOT_DIR / "app"), quiet=1)
    ok_scripts = compileall.compile_dir(str(ROOT_DIR / "scripts"), quiet=1)
    if not (ok_app and ok_scripts):
        raise AssertionError("Compilacion Python con errores en app/ o scripts/")
    return "Compilacion de app/ y scripts/ sin errores"


def check_runtime_dependencies() -> str:
    modules = [
        "bcrypt",
        "httpx",
        "customtkinter",
        "supabase",
        "dotenv",
    ]
    missing: list[str] = []
    for module in modules:
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    if missing:
        raise AssertionError(
            "Faltan dependencias Python: "
            f"{missing}. Instala requirements en tu entorno (.venv recomendado)."
        )
    return f"{len(modules)} dependencias cargadas"


def check_domain_auth() -> str:
    from domain.auth import Role

    assert Role.from_raw("GERENTE") == Role.GERENTE
    assert Role.from_raw("dueño") == Role.DUENIO
    assert Role.from_raw("dueno") == Role.DUENIO
    assert Role.from_raw("admin") == Role.DUENIO
    expect_raises(ValueError, Role.from_raw, "NO_EXISTE")
    return "Normalizacion de roles valida"


def check_domain_calculos() -> str:
    from domain import calc
    from domain import corte

    assert calc.calcular_subtotal(22.5, 2) == 45.0
    assert calc.calcular_total([{"subtotal": 10}, {"subtotal": 15.37}]) == 25.37

    rows = [
        {"metodo_pago": "EFECTIVO", "total": 100},
        {"metodo_pago": "TARJETA", "total": 50.5},
        {"metodo_pago": "TRANSFER", "total": 20},
        {"metodo_pago": "OTRO", "total": 10},
    ]
    resumen = corte.calc_ventas_por_metodo(rows)
    assert resumen["EFECTIVO"] == 100.0
    assert resumen["TARJETA"] == 50.5
    assert resumen["TRANSFER"] == 20.0
    assert resumen["total"] == 180.5

    efectivo = corte.calc_efectivo_teorico(ventas_efectivo=100, gastos_total=20, propinas_tarjeta_total=10, caja_chica_inicial=50)
    assert efectivo == 120.0
    assert corte.calc_diferencia(130, efectivo) == 10.0
    return "Funciones de calculo con resultados esperados"


def check_domain_models() -> str:
    from domain.models import ComandaDraft, Gasto, MetodoPago, Producto, Propina

    p = Producto.from_inputs("Taco", "COMIDA", 35.5, venta_por_gramo=False, orden_catalogo=7)
    record = p.to_record()
    assert record["nombre"] == "Taco"
    assert record["precio"] == 35.5
    expect_raises(ValueError, Producto.from_inputs, "X", "C", -1)

    g = Gasto.from_inputs("Limon", "INSUMO", 120, metodo_pago="EFECTIVO")
    assert g.to_record()["metodo_pago"] == MetodoPago.EFECTIVO.value
    expect_raises(ValueError, Gasto.from_inputs, "X", "C", 10, metodo_pago="CRYPTO")

    propina = Propina.from_inputs(50, fuente="manual")
    assert propina.to_record()["fuente"] == "NO_ESPECIFICADO"

    draft = ComandaDraft.from_raw(
        mesero="Ana",
        metodo_pago="TARJETA",
        total=230,
        recibido=None,
        cambio=None,
        items=[
            {
                "producto_id": 1,
                "nombre_snapshot": "Consome",
                "precio_unitario": 80,
                "cantidad": 2,
                "subtotal": 160,
            }
        ],
        propina=20,
    )
    assert draft.metodo_pago == MetodoPago.TARJETA
    assert len(draft.items) == 1
    return "Modelos de dominio con validaciones correctas"


def check_ticket_builders() -> str:
    from domain.ticket import build_corte_ticket_text, build_ticket_text

    ticket = build_ticket_text(
        {
            "negocio": "AutoNoma",
            "folio": 123,
            "fecha_hora": "2026-02-17 19:00",
            "mesa": "3",
            "mesero": "Luis",
            "metodo_pago": "EFECTIVO",
            "propina": 15,
            "total": 215,
            "items": [{"nombre_snapshot": "Taco", "cantidad": 2, "subtotal": 200}],
        }
    )
    assert "Folio: 123" in ticket
    assert "TOTAL:" in ticket

    corte = build_corte_ticket_text(
        {
            "fecha": "2026-02-17",
            "estado": "ABIERTO",
            "caja_chica_inicial": 100,
            "efectivo_contado": 400,
            "efectivo_teorico": 390,
            "diferencia": 10,
            "total_ventas": 1000,
            "ventas_efectivo": 500,
            "ventas_tarjeta": 300,
            "ventas_transfer": 200,
            "total_gastos": 100,
            "total_terminal": 340,
            "propinas_tarjeta": 40,
            "propinas_efectivo": 20,
            "propinas_total": 60,
            "propinas_detalle": [{"mesero": "Luis", "total_pagar": 60, "total_tarjeta": 40, "total_efectivo": 20}],
        }
    )
    assert "CORTE DEL DIA" in corte
    assert "REPARTO PROPINAS" in corte
    return "Generacion de tickets correcta"


def check_offline_ops() -> str:
    from services.offline_ops import (
        CierreOperation,
        ComandaOperation,
        GastoOperation,
        PropinaOperation,
        operation_from_record,
    )

    class FakeSync:
        def __init__(self):
            self.calls: list[str] = []

        def sync_gasto(self, payload: dict) -> None:
            self.calls.append(f"gasto:{payload.get('id', 'n/a')}")

        def sync_propina(self, payload: dict) -> None:
            self.calls.append(f"propina:{payload.get('id', 'n/a')}")

        def sync_cierre(self, payload: dict) -> None:
            self.calls.append(f"cierre:{payload.get('id', 'n/a')}")

        def sync_comanda(self, payload: dict) -> None:
            self.calls.append(f"comanda:{payload.get('id', 'n/a')}")

    target = FakeSync()
    GastoOperation({"id": 1}).apply(target)
    PropinaOperation({"id": 2}).apply(target)
    CierreOperation({"id": 3}).apply(target)
    ComandaOperation({"id": 4}).apply(target)
    assert len(target.calls) == 4

    unknown = operation_from_record("desconocida", {"id": 9})
    expect_raises(ValueError, unknown.apply, target)
    return "Registro y ejecucion de operaciones offline correctos"


def check_offline_store() -> str:
    from services.offline_ops import GastoOperation, PropinaOperation
    from services.offline_store import OfflineStore

    with tempfile.TemporaryDirectory(prefix="barbacoa_validate_offline_") as tmpdir:
        store = OfflineStore(tmpdir)
        store.enqueue(GastoOperation({"id": 1, "monto": 100}))
        store.enqueue(PropinaOperation({"id": 2, "monto": 25}))

        ops = store.list_ops()
        assert len(ops) == 2

        store.delete_op(ops[0].record_id)
        ops_after_delete = store.list_ops()
        assert len(ops_after_delete) == 1

        store.daily_backup(tmpdir)
        backup_dir = Path(tmpdir) / "data" / "backups"
        backups = list(backup_dir.glob("offline_*.json"))
        assert len(backups) == 1

        backup_data = json.loads(backups[0].read_text(encoding="utf-8"))
        assert isinstance(backup_data.get("ops"), list)
    return "Persistencia offline (enqueue/list/delete/backup) correcta"


def check_auth_service_local() -> str:
    base_env: dict[str, str] = {}
    if not supabase_env_ready():
        base_env["SUPABASE_URL"] = "https://example.invalid"
        base_env["SUPABASE_KEY"] = "dummy"

    class FakeDB:
        def __init__(self) -> None:
            self.users: dict[str, dict] = {}

        def get_user_by_role(self, role: str) -> dict | None:
            user = self.users.get(role)
            return dict(user) if user else None

        def set_role_pin(self, role: str, password_hash: str, **_kwargs) -> dict:
            current = self.users.get(role) or {"rol": role, "activo": True}
            current["password_hash"] = password_hash
            self.users[role] = current
            return dict(current)

    with tempfile.TemporaryDirectory(prefix="barbacoa_validate_auth_") as tmpdir:
        with patched_env(
            {
                **base_env,
                "BARBACOA_RECOVERY_EMAIL_TO": "sistemamirandapos@gmail.com",
                "BARBACOA_SMTP_USER": "dummy@example.com",
                "BARBACOA_SMTP_PASSWORD": "dummy",
                "BARBACOA_SMTP_HOST": "smtp.gmail.com",
                "BARBACOA_SMTP_PORT": "587",
            }
        ):
            try:
                import bcrypt
                from services.auth_service import AuthService
            except ModuleNotFoundError as exc:
                raise SkipCheck(f"Omitido por dependencia faltante: {exc.name}") from exc

            db = FakeDB()
            pin_hash = bcrypt.hashpw("1234".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            db.users["DUENIO"] = {
                "rol": "DUENIO",
                "activo": True,
                "password_hash": pin_hash,
            }

            auth = AuthService(db)  # type: ignore[arg-type]
            auth._cache_path = str(Path(tmpdir) / "auth_cache.json")
            auth._recovery_path = str(Path(tmpdir) / "recovery_codes.json")

            bad = auth.unlock("DUENIO", "12")
            assert not bad.success

            ok = auth.unlock("DUENIO", "1234")
            assert ok.success
            assert auth.current_role().value == "DUENIO"
            assert auth.can("REPORTES")

            auth.lock()
            assert auth.current_role().value == "MESERO"

            sent_codes: list[str] = []

            def fake_send(_role, code: str) -> None:
                sent_codes.append(code)

            auth._send_recovery_email = fake_send  # type: ignore[method-assign]

            req = auth.request_recovery_code("DUENIO")
            assert req.success
            assert len(sent_codes) == 1
            code = sent_codes[0]

            recover = auth.recover_pin("DUENIO", code, "4321")
            assert recover.success

            used_again = auth.recover_pin("DUENIO", code, "9999")
            assert not used_again.success

            auth.lock()
            with_new_pin = auth.unlock("DUENIO", "4321")
            assert with_new_pin.success
    return "Auth local (unlock + recuperacion OTP) correcta"


def check_corte_service_update_caja() -> str:
    base_env: dict[str, str] = {}
    if not supabase_env_ready():
        base_env["SUPABASE_URL"] = "https://example.invalid"
        base_env["SUPABASE_KEY"] = "dummy"
    with patched_env(base_env):
        try:
            import services.corte_service as corte_service
        except ModuleNotFoundError as exc:
            raise SkipCheck(f"Omitido por dependencia faltante: {exc.name}") from exc

        class FakeResponse:
            def __init__(self, data: list[dict]):
                self.data = data

        class FakeTable:
            def __init__(self):
                self.updated: dict | None = None
                self.where: tuple[str, str] | None = None

            def update(self, data: dict):
                self.updated = data
                return self

            def eq(self, column: str, value: str):
                self.where = (column, value)
                return self

            def execute(self):
                return FakeResponse(
                    [
                        {
                            "id": "cierre-1",
                            "estado": "ABIERTO",
                            "caja_chica_inicial": float((self.updated or {}).get("caja_chica_inicial") or 0),
                        }
                    ]
                )

        class FakeClient:
            def __init__(self):
                self.table_ref = FakeTable()

            def table(self, name: str):
                if name != "cierres_caja":
                    raise AssertionError(f"Tabla inesperada: {name}")
                return self.table_ref

        class FakeDB:
            def __init__(self):
                self.client = FakeClient()

        fake_db = FakeDB()
        original_get_corte = corte_service.get_corte_por_fecha
        try:
            corte_service.get_corte_por_fecha = lambda _fecha, db=None: {"id": "cierre-1", "estado": "ABIERTO"}
            updated = corte_service.actualizar_caja_chica_jornada(
                date.today(),
                250.75,
                db=fake_db,
            )
            assert updated["caja_chica_inicial"] == 250.75
            assert fake_db.client.table_ref.where == ("id", "cierre-1")

            corte_service.get_corte_por_fecha = lambda _fecha, db=None: {"id": "cierre-1", "estado": "CERRADO"}
            expect_raises(
                ValueError,
                corte_service.actualizar_caja_chica_jornada,
                date.today(),
                120,
                fake_db,
            )

            corte_service.get_corte_por_fecha = lambda _fecha, db=None: None
            expect_raises(
                ValueError,
                corte_service.actualizar_caja_chica_jornada,
                date.today(),
                120,
                fake_db,
            )
        finally:
            corte_service.get_corte_por_fecha = original_get_corte

    return "Actualizacion de caja chica en jornada abierta validada"


def check_online_supabase() -> str:
    try:
        from services.supabase_service import SupabaseService
    except ModuleNotFoundError as exc:
        raise SkipCheck(f"Omitido por dependencia faltante: {exc.name}") from exc

    db = SupabaseService()
    productos = db.listar_productos()
    meseros = db.listar_meseros_activos()
    roles = db.listar_usuarios_roles()
    return (
        "Conexion online Supabase OK "
        f"(productos={len(productos)}, meseros_activos={len(meseros)}, roles={len(roles)})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida componentes clave del POS y reporta OK/ERROR por chequeo."
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Incluye chequeos de conexion real a Supabase.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Muestra stacktrace completo en checks con ERROR.",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT_DIR / ".env")
    except Exception:
        pass

    validator = Validator(verbose=args.verbose)
    print("Iniciando validaciones del sistema...\n")

    validator.run("Python version", check_python_version)
    validator.run("Rutas clave del proyecto", check_required_paths)
    validator.run("Compilacion Python (app y scripts)", check_compileall)
    validator.run("Dependencias Python", check_runtime_dependencies)
    validator.run("Dominio auth (roles)", check_domain_auth)
    validator.run("Dominio calculos", check_domain_calculos)
    validator.run("Dominio modelos", check_domain_models)
    validator.run("Tickets (venta y corte)", check_ticket_builders)
    validator.run("Operaciones offline", check_offline_ops)
    validator.run("Store offline (SQLite)", check_offline_store)
    validator.run("Auth service local", check_auth_service_local)
    validator.run("Corte service (modificar caja chica)", check_corte_service_update_caja)

    if args.online:
        validator.run("Supabase online", check_online_supabase)
    else:
        validator.run("Supabase online", lambda: (_ for _ in ()).throw(SkipCheck("Omitido. Usa --online para incluirlo.")))

    validator.print_summary()
    return 1 if validator.has_errors() else 0


if __name__ == "__main__":
    raise SystemExit(main())
