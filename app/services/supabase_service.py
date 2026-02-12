from __future__ import annotations

from datetime import date, datetime, time, timezone
import logging
import os
import threading
from zoneinfo import ZoneInfo

from supabase import create_client
from supabase.lib.client_options import ClientOptions

from domain.models import (
    CierreCaja,
    ComandaDraft,
    ComandaItem,
    Gasto,
    Mesero,
    MetodoPago,
    Producto,
    Propina,
)
from .offline_ops import (
    CierreOperation,
    ComandaOperation,
    GastoOperation,
    OfflineSync,
    PropinaOperation,
)
from .offline_store import OfflineStore
from .repositories import (
    CierresRepository,
    ComandaItemsRepository,
    ComandasRepository,
    GastosRepository,
    MeserosRepository,
    ProductosRepository,
    PropinasRepository,
    UsuariosRepository,
)
from .settings import SUPABASE_KEY, SUPABASE_URL
from .settings import SUPABASE_TIMEOUT_SECONDS
from .settings import BARBACOA_TIMEZONE


class SupabaseService(OfflineSync):
    """Fachada de acceso a datos para el POS.

    - Encapsula repositorios por tabla.
    - Valida entradas con modelos de dominio.
    - Maneja cola offline con polimorfismo.
    """

    def __init__(self) -> None:
        options = ClientOptions(postgrest_client_timeout=SUPABASE_TIMEOUT_SECONDS)
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.offline = OfflineStore(base_dir)
        self._base_dir = base_dir
        self._logger = logging.getLogger("barbacoa.pos.supabase")
        self._business_tz = self._load_business_timezone()

        self.productos_repo = ProductosRepository(self.client)
        self.meseros_repo = MeserosRepository(self.client)
        self.comandas_repo = ComandasRepository(self.client)
        self.items_repo = ComandaItemsRepository(self.client)
        self.gastos_repo = GastosRepository(self.client)
        self.propinas_repo = PropinasRepository(self.client)
        self.cierres_repo = CierresRepository(self.client)
        self.usuarios_repo = UsuariosRepository(self.client)

        self._start_legacy_role_migration_async()

    # ---------------- Productos ----------------
    def get_productos(self) -> list[dict]:
        productos = self.productos_repo.list_activos()
        return [p.to_record() for p in productos]

    def listar_productos(self) -> list[dict]:
        productos = self.productos_repo.list_all()
        return [p.to_record() for p in productos]

    def crear_producto(
        self,
        nombre: str,
        categoria: str,
        precio: float,
        activo: bool = True,
        venta_por_gramo: bool = False,
        orden_catalogo: int = 1000,
    ) -> dict:
        producto = Producto.from_inputs(
            nombre=nombre,
            categoria=categoria,
            precio=precio,
            activo=activo,
            venta_por_gramo=venta_por_gramo,
            orden_catalogo=orden_catalogo,
        )
        creado = self.productos_repo.create(producto)
        return creado.to_record()

    def actualizar_producto(
        self,
        producto_id: int,
        nombre: str | None = None,
        categoria: str | None = None,
        precio: float | None = None,
        activo: bool | None = None,
        venta_por_gramo: bool | None = None,
        orden_catalogo: int | None = None,
    ) -> dict:
        if producto_id is None:
            raise ValueError("producto_id es obligatorio")

        changes: dict = {}
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("nombre es obligatorio")
            changes["nombre"] = nombre.strip()
        if categoria is not None:
            if not categoria.strip():
                raise ValueError("categoria es obligatoria")
            changes["categoria"] = categoria.strip()
        if precio is not None:
            if float(precio) < 0:
                raise ValueError("precio debe ser >= 0")
            changes["precio"] = round(float(precio), 2)
        if activo is not None:
            changes["activo"] = bool(activo)
        if venta_por_gramo is not None:
            changes["venta_por_gramo"] = bool(venta_por_gramo)
        if orden_catalogo is not None:
            try:
                orden = int(orden_catalogo)
            except Exception as exc:
                raise ValueError("orden_catalogo debe ser un entero >= 0") from exc
            if orden < 0:
                raise ValueError("orden_catalogo debe ser >= 0")
            changes["orden_catalogo"] = orden
        if not changes:
            raise ValueError("no hay cambios para actualizar")

        actualizado = self.productos_repo.update_fields(producto_id, changes)
        return actualizado.to_record()

    # ---------------- Comandas ----------------
    def crear_comanda(
        self,
        mesero: str,
        metodo_pago: str,
        total: float,
        recibido: float | None,
        cambio: float | None,
    ) -> dict:
        draft = ComandaDraft.from_raw(
            mesero=mesero,
            metodo_pago=metodo_pago,
            total=total,
            recibido=recibido,
            cambio=cambio,
            items=[],
            propina=None,
        )
        return self.comandas_repo.create(draft)

    def guardar_comanda(
        self,
        mesero: str,
        metodo_pago: str,
        total: float,
        recibido: float | None,
        cambio: float | None,
        items: list[dict],
        propina: float | None = None,
    ) -> dict:
        draft = ComandaDraft.from_raw(
            mesero=mesero,
            metodo_pago=metodo_pago,
            total=total,
            recibido=recibido,
            cambio=cambio,
            items=items,
            propina=propina,
        )

        try:
            return self._insert_comanda(draft)
        except Exception:
            self.offline.enqueue(ComandaOperation(draft.to_offline_payload()))
            return {"offline": True}

    def agregar_items(self, comanda_id: str, items: list[dict]) -> None:
        parsed_items = [ComandaItem.from_raw(it) for it in items]
        self.items_repo.insert_many(comanda_id, parsed_items)

    def _insert_comanda(self, draft: ComandaDraft) -> dict:
        comanda = self.comandas_repo.create(draft)
        if draft.items:
            self.items_repo.insert_many(comanda["id"], draft.items)

        if draft.propina is not None and draft.propina > 0:
            propina = Propina.from_inputs(
                monto=draft.propina,
                mesero_id=None,
                mesero_nombre_snapshot=draft.mesero or "Sin nombre",
                fuente=draft.metodo_pago.value,
                comanda_id=comanda["id"],
            )
            self.propinas_repo.create(propina)
        return comanda

    # ---------------- Gastos ----------------
    def crear_gasto(
        self,
        concepto: str,
        categoria: str,
        monto: float,
        nota: str | None = None,
        metodo_pago: str = MetodoPago.EFECTIVO.value,
    ) -> dict:
        gasto = Gasto.from_inputs(
            concepto=concepto,
            categoria=categoria,
            monto=monto,
            nota=nota,
            metodo_pago=metodo_pago,
        )
        try:
            return self.gastos_repo.create(gasto)
        except Exception:
            self.offline.enqueue(GastoOperation(gasto.to_record()))
            return {"offline": True}

    def listar_gastos_dia(self, fecha: date) -> list[dict]:
        desde, hasta = self._day_range(fecha)
        return self.gastos_repo.list_by_range(desde, hasta)

    # ---------------- Meseros ----------------
    def listar_meseros_activos(self) -> list[dict]:
        meseros = self.meseros_repo.list_activos()
        return [m.to_record() for m in meseros]

    def listar_meseros(self) -> list[dict]:
        meseros = self.meseros_repo.list_all()
        return [m.to_record() for m in meseros]

    def crear_mesero(self, nombre: str, activo: bool = True) -> dict:
        mesero = Mesero.from_inputs(nombre=nombre, activo=activo)
        creado = self.meseros_repo.create(mesero)
        return creado.to_record()

    def actualizar_mesero(self, mesero_id: str, nombre: str | None = None, activo: bool | None = None) -> dict:
        if not mesero_id:
            raise ValueError("mesero_id es obligatorio")
        changes: dict = {}
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("nombre es obligatorio")
            changes["nombre"] = nombre.strip()
        if activo is not None:
            changes["activo"] = bool(activo)
        if not changes:
            raise ValueError("no hay cambios para actualizar")

        actualizado = self.meseros_repo.update_fields(mesero_id, changes)
        return actualizado.to_record()

    def eliminar_mesero(self, mesero_id: str) -> None:
        if not mesero_id:
            raise ValueError("mesero_id es obligatorio")
        self.meseros_repo.delete(mesero_id)

    # ---------------- Propinas ----------------
    def crear_propina(
        self,
        monto: float,
        mesero_id: str | None = None,
        mesero_nombre_snapshot: str | None = None,
        fuente: str = "NO_ESPECIFICADO",
        comanda_id: str | None = None,
    ) -> dict:
        propina = Propina.from_inputs(
            monto=monto,
            mesero_id=mesero_id,
            mesero_nombre_snapshot=mesero_nombre_snapshot,
            fuente=fuente,
            comanda_id=comanda_id,
        )
        try:
            return self.propinas_repo.create(propina)
        except Exception:
            self.offline.enqueue(PropinaOperation(propina.to_record()))
            return {"offline": True}

    def listar_propinas_rango(self, desde: datetime, hasta: datetime) -> list[dict]:
        if not isinstance(desde, datetime) or not isinstance(hasta, datetime):
            raise ValueError("desde y hasta deben ser datetime")
        if hasta < desde:
            raise ValueError("hasta debe ser >= desde")
        return self.propinas_repo.list_by_range(desde.isoformat(), hasta.isoformat())

    def _aggregate_propinas_rows(self, rows: list[dict]) -> list[dict]:
        agg: dict[str, dict] = {}
        for r in rows:
            mesero_id = r.get("mesero_id")
            mesero_name = r.get("mesero_nombre_snapshot") or None
            key = mesero_id or mesero_name or "SIN_NOMBRE"
            label = mesero_name or mesero_id or "Sin nombre"
            fuente = str(r.get("fuente") or "").strip().upper()
            if fuente in {"MANUAL", "COMANDA", ""}:
                fuente = "NO_ESPECIFICADO"
            if fuente not in {"EFECTIVO", "TARJETA", "TRANSFER", "NO_ESPECIFICADO"}:
                fuente = "NO_ESPECIFICADO"
            monto = float(r.get("monto") or 0)

            if key not in agg:
                agg[key] = {
                    "mesero": label,
                    "total_propinas": 0.0,
                    "num_propinas": 0,
                    "num_tarjeta": 0,
                    "total_tarjeta": 0.0,
                    "num_efectivo": 0,
                    "num_transfer": 0,
                    "num_no_especificado": 0,
                }

            agg[key]["total_propinas"] += monto
            agg[key]["num_propinas"] += 1
            if fuente == "TARJETA":
                agg[key]["num_tarjeta"] += 1
                agg[key]["total_tarjeta"] += monto
            elif fuente == "EFECTIVO":
                agg[key]["num_efectivo"] += 1
            elif fuente == "TRANSFER":
                agg[key]["num_transfer"] += 1
            else:
                agg[key]["num_no_especificado"] += 1

        result = list(agg.values())
        result.sort(
            key=lambda x: (
                -x["num_tarjeta"],
                -x["total_tarjeta"],
                -x["total_propinas"],
                x["mesero"],
            )
        )
        return result

    def reporte_propinas_dia(self, fecha: date) -> list[dict]:
        if not isinstance(fecha, date):
            raise ValueError("fecha debe ser date")
        desde, hasta = self._day_range(fecha)
        rows = self.propinas_repo.list_by_range(desde, hasta)
        return self._aggregate_propinas_rows(rows)

    def reporte_propinas_mes(self, year: int, month: int) -> list[dict]:
        if month < 1 or month > 12:
            raise ValueError("month debe estar entre 1 y 12")

        desde, hasta = self._month_range(year, month)
        rows = self.listar_propinas_rango(desde, hasta)
        return self._aggregate_propinas_rows(rows)

    # ---------------- Cierre de caja ----------------
    def obtener_cierre(self, fecha: date) -> dict | None:
        return self.cierres_repo.get_by_fecha(fecha.isoformat())

    def crear_cierre(self, fecha: date, efectivo_reportado: float, notas: str | None = None) -> dict:
        if efectivo_reportado is None or float(efectivo_reportado) < 0:
            raise ValueError("efectivo_reportado debe ser >= 0")

        existente = self.obtener_cierre(fecha)
        if existente:
            raise ValueError(f"Ya existe un cierre para la fecha {fecha.isoformat()}")

        desde, hasta = self._day_range(fecha)

        ventas_rows = (
            self.client.table("comandas")
            .select("total, metodo_pago")
            .gte("created_at", desde)
            .lte("created_at", hasta)
            .execute()
        ).data or []

        total_ventas = sum(float(r.get("total") or 0) for r in ventas_rows)
        ventas_efectivo = sum(
            float(r.get("total") or 0) for r in ventas_rows if r.get("metodo_pago") == "EFECTIVO"
        )

        gastos_rows = (
            self.client.table("gastos")
            .select("monto")
            .gte("created_at", desde)
            .lte("created_at", hasta)
            .execute()
        ).data or []

        total_gastos = sum(float(r.get("monto") or 0) for r in gastos_rows)
        neto = total_ventas - total_gastos
        diferencia_efectivo = float(efectivo_reportado) - ventas_efectivo

        cierre = CierreCaja(
            fecha=fecha,
            total_ventas=total_ventas,
            total_gastos=total_gastos,
            neto=neto,
            efectivo_reportado=float(efectivo_reportado),
            diferencia_efectivo=diferencia_efectivo,
            notas=notas,
        )

        try:
            return self.cierres_repo.create(cierre)
        except Exception:
            self.offline.enqueue(CierreOperation(cierre.to_record()))
            return {"offline": True}

    # ---------------- Offline sync ----------------
    def sync_offline(self) -> int:
        synced = 0
        for record in self.offline.list_ops():
            try:
                record.operation.apply(self)
            except Exception:
                continue
            self.offline.delete_op(record.record_id)
            synced += 1
        return synced

    def sync_gasto(self, payload: dict) -> None:
        gasto = Gasto.from_inputs(
            concepto=payload.get("concepto", ""),
            categoria=payload.get("categoria", ""),
            monto=payload.get("monto", 0),
            nota=payload.get("nota"),
            metodo_pago=payload.get("metodo_pago", MetodoPago.EFECTIVO.value),
        )
        self.gastos_repo.create(gasto)

    def sync_propina(self, payload: dict) -> None:
        propina = Propina.from_inputs(
            monto=payload.get("monto", 0),
            mesero_id=payload.get("mesero_id"),
            mesero_nombre_snapshot=payload.get("mesero_nombre_snapshot"),
            fuente=payload.get("fuente", "NO_ESPECIFICADO"),
            comanda_id=payload.get("comanda_id"),
        )
        self.propinas_repo.create(propina)

    def sync_cierre(self, payload: dict) -> None:
        cierre = CierreCaja(
            fecha=date.fromisoformat(payload["fecha"]),
            total_ventas=float(payload["total_ventas"]),
            total_gastos=float(payload["total_gastos"]),
            neto=float(payload["neto"]),
            efectivo_reportado=float(payload["efectivo_reportado"]),
            diferencia_efectivo=float(payload["diferencia_efectivo"]),
            notas=payload.get("notas"),
        )
        self.cierres_repo.create(cierre)

    def sync_comanda(self, payload: dict) -> None:
        draft = ComandaDraft.from_raw(
            mesero=payload.get("mesero", ""),
            metodo_pago=payload.get("metodo_pago", MetodoPago.EFECTIVO.value),
            total=payload.get("total", 0),
            recibido=payload.get("recibido"),
            cambio=payload.get("cambio"),
            items=payload.get("items", []),
            propina=payload.get("propina"),
        )
        self._insert_comanda(draft)

    # ---------------- Usuarios / Roles ----------------
    def _start_legacy_role_migration_async(self) -> None:
        if not self._should_run_legacy_role_migration():
            return

        def _job():
            try:
                self.usuarios_repo.migrate_admin_to_duenio()
            except Exception:
                # No bloquear arranque por migracion legacy.
                self._logger.debug("legacy role migration skipped", exc_info=True)
                return
            self._mark_legacy_role_migration_ran()

        threading.Thread(target=_job, daemon=True, name="legacy-role-migration").start()

    def _legacy_role_migration_stamp_path(self) -> str:
        return os.path.join(self._base_dir, "data", "last_legacy_role_migration.txt")

    def _should_run_legacy_role_migration(self) -> bool:
        path = self._legacy_role_migration_stamp_path()
        today = date.today().isoformat()
        try:
            with open(path, "r", encoding="utf-8") as f:
                last = (f.read() or "").strip()
            return last != today
        except Exception:
            return True

    def _mark_legacy_role_migration_ran(self) -> None:
        path = self._legacy_role_migration_stamp_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(date.today().isoformat())

    def _migrate_legacy_admin_role(self) -> None:
        try:
            self.usuarios_repo.migrate_admin_to_duenio()
        except Exception:
            # La tabla puede no existir aun o no tener permisos de update.
            pass

    def get_user_by_role(self, role: str) -> dict | None:
        user = self.usuarios_repo.get_by_role(role)
        return user.to_record() if user else None

    def listar_usuarios_roles(self) -> list[dict]:
        users = self.usuarios_repo.list_roles()
        return [u.to_record() for u in users]

    def set_role_pin(
        self,
        role: str,
        password_hash: str,
        *,
        nombre: str | None = None,
        usuario: str | None = None,
    ) -> dict:
        if not password_hash or not str(password_hash).strip():
            raise ValueError("password_hash es obligatorio")
        saved = self.usuarios_repo.set_role_pin(
            role=role,
            password_hash=str(password_hash).strip(),
            nombre=nombre,
            usuario=usuario,
        )
        return saved.to_record()

    def set_role_active(self, role: str, active: bool) -> dict:
        updated = self.usuarios_repo.set_role_active(role, bool(active))
        return updated.to_record()

    # ---------------- Helpers ----------------
    def _load_business_timezone(self):
        raw = BARBACOA_TIMEZONE
        if raw:
            try:
                return ZoneInfo(raw)
            except Exception:
                self._logger.warning("BARBACOA_TIMEZONE invalida: %s. Se usa zona local del sistema.", raw)
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz or timezone.utc

    def _month_range(self, year: int, month: int) -> tuple[datetime, datetime]:
        start_local = datetime(year, month, 1, tzinfo=self._business_tz)
        if month == 12:
            next_local = datetime(year + 1, 1, 1, tzinfo=self._business_tz)
        else:
            next_local = datetime(year, month + 1, 1, tzinfo=self._business_tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = next_local.astimezone(timezone.utc) - datetime.resolution
        return start_utc, end_utc

    def _day_range(self, fecha: date) -> tuple[str, str]:
        start_local = datetime.combine(fecha, time.min, tzinfo=self._business_tz)
        end_local = datetime.combine(fecha, time.max, tzinfo=self._business_tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        return start_utc.isoformat(), end_utc.isoformat()
