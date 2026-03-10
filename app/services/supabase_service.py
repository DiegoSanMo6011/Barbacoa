from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
import logging
import os
import threading
from zoneinfo import ZoneInfo

import httpx
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
    Insumo,
    Receta,
    MovimientoInventario,
)
from domain.ticket import build_ticket_text
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
    ComandaCorreccionesRepository,
    ComandaItemsRepository,
    ComandaPagosRepository,
    ComandasRepository,
    GastosRepository,
    MeserosRepository,
    ProductosRepository,
    PropinasRepository,
    TicketHistorialRepository,
    UsuariosRepository,
    InsumosRepository,
    RecetasRepository,
    MovimientosInventarioRepository,
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
        self.pagos_repo = ComandaPagosRepository(self.client)
        self.correcciones_repo = ComandaCorreccionesRepository(self.client)
        self.ticket_historial_repo = TicketHistorialRepository(self.client)
        self.gastos_repo = GastosRepository(self.client)
        self.propinas_repo = PropinasRepository(self.client)
        self.cierres_repo = CierresRepository(self.client)
        self.usuarios_repo = UsuariosRepository(self.client)
        self.insumos_repo = InsumosRepository(self.client)
        self.recetas_repo = RecetasRepository(self.client)
        self.movimientos_inv_repo = MovimientosInventarioRepository(self.client)

        self._start_legacy_role_migration_async()

    @staticmethod
    def _should_enqueue_offline(exc: Exception) -> bool:
        if isinstance(exc, ValueError):
            return False
        if isinstance(exc, (httpx.RequestError, TimeoutError)):
            return True

        msg = str(exc).lower()
        err_type = exc.__class__.__name__.lower()

        non_transient_tokens = (
            "bad request",
            "violates",
            "constraint",
            "duplicate key",
            "invalid input",
            "out of range",
            "overflow",
            "permission denied",
            "not null",
            "foreign key",
            "unique",
            "schema cache",
            "column",
            "check constraint",
            "http/2 400",
        )
        if any(token in msg for token in non_transient_tokens):
            return False

        transient_tokens = (
            "timeout",
            "timed out",
            "connection",
            "network",
            "name resolution",
            "temporary failure",
            "dns",
            "unreachable",
            "service unavailable",
            "gateway timeout",
            "connection refused",
            "connection reset",
        )
        return any(token in msg for token in transient_tokens) or "connecterror" in err_type

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
        mesa: str | None = None,
        pagos: list[dict] | None = None,
    ) -> dict:
        draft = ComandaDraft.from_raw(
            mesero=mesero,
            metodo_pago=metodo_pago,
            total=total,
            recibido=recibido,
            cambio=cambio,
            mesa=mesa,
            items=[],
            propina=None,
            pagos=pagos,
        )
        return self.comandas_repo.create(draft)

    def guardar_comanda(
        self,
        mesero: str,
        mesa: str,
        metodo_pago: str,
        total: float,
        recibido: float | None,
        cambio: float | None,
        items: list[dict],
        propina: float | None = None,
        pagos: list[dict] | None = None,
    ) -> dict:
        draft = ComandaDraft.from_raw(
            mesero=mesero,
            metodo_pago=metodo_pago,
            total=total,
            recibido=recibido,
            cambio=cambio,
            mesa=mesa,
            items=items,
            propina=propina,
            pagos=pagos,
        )

        try:
            return self._insert_comanda(draft)
        except Exception as exc:
            if not self._should_enqueue_offline(exc):
                raise
            self.offline.enqueue(ComandaOperation(draft.to_offline_payload()))
            return {"offline": True}

    def agregar_items(self, comanda_id: str, items: list[dict]) -> None:
        parsed_items = [ComandaItem.from_raw(it) for it in items]
        self.items_repo.insert_many(comanda_id, parsed_items)

    def _insert_comanda(self, draft: ComandaDraft) -> dict:
        comanda = self.comandas_repo.create(draft)
        if draft.items:
            self.items_repo.insert_many(comanda["id"], draft.items)
            try:
                # Deduct inventory for all items in the comanda
                self.descontar_inventario_por_comanda(
                    comanda["id"], [item.to_record() for item in draft.items]
                )
            except Exception as e:
                self._logger.error(f"Error descontando inventario para comanda {comanda['id']}: {e}")
        self.guardar_pagos_comanda(comanda["id"], draft.pagos)
        self._replace_comanda_tips(comanda["id"], draft.mesero, draft.pagos)
        return comanda

    def guardar_pagos_comanda(self, comanda_id: str, pagos: list[dict]) -> list[dict]:
        pagos = list(pagos or [])
        if not pagos:
            return []
        try:
            return self.pagos_repo.replace_for_comanda(comanda_id, pagos)
        except Exception as exc:
            msg = str(exc).lower()
            table_missing = (
                "comanda_pagos" in msg
                and ("does not exist" in msg or "relation" in msg or "schema cache" in msg or "column" in msg)
            )
            if table_missing:
                if len(pagos) > 1:
                    raise ValueError(
                        "Falta migración SQL para pagos mixtos. Ejecuta `sql/comandas_pagos_auditoria.sql`."
                    ) from exc
                # Compatibilidad legacy: sin tabla comanda_pagos solo se conserva metodo principal en comandas.
                return []
            raise

    def _replace_comanda_tips(self, comanda_id: str, mesero: str, pagos: list[dict]) -> None:
        try:
            self.client.table("propinas").delete().eq("comanda_id", comanda_id).execute()
        except Exception:
            # No bloquear guardado por limpieza de propinas legacy.
            pass
        for pago in pagos:
            tip = float(pago.get("propina") or 0)
            if tip <= 0:
                continue
            fuente = str(pago.get("metodo_pago") or "NO_ESPECIFICADO").strip().upper()
            propina = Propina.from_inputs(
                monto=tip,
                mesero_id=None,
                mesero_nombre_snapshot=mesero or "Sin nombre",
                fuente=fuente,
                comanda_id=comanda_id,
            )
            self.propinas_repo.create(propina)

    def listar_historial_comandas(
        self,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        folio: str | None = None,
        mesero: str | None = None,
        mesa: str | None = None,
    ) -> list[dict]:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")
        desde, _ = self._day_range(fecha_inicio)
        _, hasta = self._day_range(fecha_fin)
        folio_int: int | None = None
        if folio and str(folio).strip():
            try:
                folio_int = int(str(folio).strip())
            except Exception as exc:
                raise ValueError("folio debe ser numérico") from exc
        rows = self.comandas_repo.list_historial(
            desde_iso=desde,
            hasta_iso=hasta,
            folio=folio_int,
            mesero=(mesero or "").strip() or None,
            mesa=(mesa or "").strip() or None,
        )
        ids = [str(r.get("id")) for r in rows if r.get("id")]
        pagos_by_comanda = self._pagos_grouped(ids)
        for row in rows:
            cid = str(row.get("id") or "")
            pagos = pagos_by_comanda.get(cid) or []
            row["pagos"] = pagos
            row["status"] = str(row.get("status") or "PAGADA").upper()
        return rows

    def get_comanda_detalle(self, comanda_id: str) -> dict:
        comanda_id = str(comanda_id or "").strip()
        if not comanda_id:
            raise ValueError("comanda_id es obligatorio")
        comanda = self.comandas_repo.get_by_id(comanda_id)
        if not comanda:
            raise ValueError("No existe la comanda seleccionada.")
        items = self.items_repo.list_by_comanda(comanda_id)
        pagos = self._pagos_grouped([comanda_id]).get(comanda_id, [])
        tickets = self.listar_tickets_historial(comanda_id)
        return {
            "comanda": comanda,
            "items": items,
            "pagos": pagos,
            "tickets": tickets,
        }

    def cancelar_comanda(self, comanda_id: str, *, motivo: str, cancelada_por: str) -> dict:
        comanda_id = str(comanda_id or "").strip()
        if not comanda_id:
            raise ValueError("comanda_id es obligatorio")
        motivo_txt = (motivo or "").strip()
        if len(motivo_txt) < 4:
            raise ValueError("motivo debe tener al menos 4 caracteres")
        existente = self.comandas_repo.get_by_id(comanda_id)
        if not existente:
            raise ValueError("No existe la comanda seleccionada.")
        if str(existente.get("status") or "").upper() == "CANCELADA":
            return existente
        payload = {
            "status": "CANCELADA",
            "cancelada_at": datetime.now(timezone.utc).isoformat(),
            "cancelada_por": (cancelada_por or "").strip().upper() or "SISTEMA",
            "cancelacion_motivo": motivo_txt,
        }
        try:
            return self.comandas_repo.update_fields(comanda_id, payload)
        except Exception as exc:
            if self._is_missing_comanda_auditoria(exc):
                raise ValueError(
                    "Falta migración SQL para cancelación/corrección. Ejecuta `sql/comandas_pagos_auditoria.sql`."
                ) from exc
            raise

    def corregir_comanda(
        self,
        comanda_id: str,
        *,
        motivo: str,
        corregido_por: str,
        total: float | None = None,
        mesa: str | None = None,
        mesero: str | None = None,
        metodo_pago: str | None = None,
        pagos: list[dict] | None = None,
        items: list[dict] | None = None,
    ) -> dict:
        comanda_id = str(comanda_id or "").strip()
        if not comanda_id:
            raise ValueError("comanda_id es obligatorio")
        motivo_txt = (motivo or "").strip()
        if len(motivo_txt) < 4:
            raise ValueError("motivo debe tener al menos 4 caracteres")

        before = self.get_comanda_detalle(comanda_id)
        base = before.get("comanda") or {}
        if str(base.get("status") or "").upper() == "CANCELADA":
            raise ValueError("No se puede corregir una comanda cancelada.")

        changes: dict = {"status": "CORREGIDA"}
        if total is not None:
            total_num = float(total)
            if total_num < 0:
                raise ValueError("total debe ser >= 0")
            changes["total"] = round(total_num, 2)
        if mesa is not None:
            changes["mesa"] = (mesa or "").strip() or None
        if mesero is not None:
            changes["mesero"] = (mesero or "").strip()
        if metodo_pago is not None:
            metodo = MetodoPago.from_raw(metodo_pago)
            changes["metodo_pago"] = metodo.value

        parsed_items: list[ComandaItem] | None = None
        if items is not None:
            if not items:
                raise ValueError("debe existir al menos un producto")
            parsed_items = []
            total_items = 0.0
            for raw in items:
                item = ComandaItem.from_raw(raw)
                if item.cantidad <= 0:
                    raise ValueError("cantidad de item debe ser > 0")
                if item.precio_unitario < 0:
                    raise ValueError("precio_unitario de item debe ser >= 0")
                item.subtotal = round(float(item.precio_unitario) * int(item.cantidad), 2)
                total_items += item.subtotal
                parsed_items.append(item)
            if total is None:
                changes["total"] = round(total_items, 2)

        if pagos is not None and pagos:
            parsed = ComandaDraft.from_raw(
                mesero=str(changes.get("mesero") or base.get("mesero") or ""),
                mesa=str(changes.get("mesa") or base.get("mesa") or ""),
                metodo_pago=str(changes.get("metodo_pago") or base.get("metodo_pago") or MetodoPago.EFECTIVO.value),
                total=float(changes.get("total") or base.get("total") or 0),
                recibido=None,
                cambio=None,
                items=[],
                pagos=pagos,
            )
            pagos = parsed.pagos
            changes["metodo_pago"] = parsed.metodo_pago.value

        try:
            self.comandas_repo.update_fields(comanda_id, changes)
        except Exception as exc:
            if self._is_missing_comanda_auditoria(exc):
                raise ValueError(
                    "Falta migración SQL para corrección. Ejecuta `sql/comandas_pagos_auditoria.sql`."
                ) from exc
            raise

        if pagos is not None:
            self.guardar_pagos_comanda(comanda_id, pagos)
            mesero_final = str(changes.get("mesero") or base.get("mesero") or "Sin nombre")
            self._replace_comanda_tips(comanda_id, mesero_final, pagos)

        if parsed_items is not None:
            self.items_repo.replace_for_comanda(comanda_id, parsed_items)

        after = self.get_comanda_detalle(comanda_id)
        try:
            self.correcciones_repo.create(
                comanda_id=comanda_id,
                motivo=motivo_txt,
                before_payload=before,
                after_payload=after,
                corregido_por=(corregido_por or "").strip().upper() or "SISTEMA",
            )
        except Exception as exc:
            if self._is_missing_table(exc, "comanda_correcciones"):
                raise ValueError(
                    "Falta migración SQL para auditoría de correcciones. Ejecuta `sql/comandas_pagos_auditoria.sql`."
                ) from exc
            raise
        return after

    def guardar_ticket_historial(
        self,
        *,
        comanda_id: str,
        ticket_text: str,
        tipo: str,
        created_by: str | None = None,
        strict: bool = False,
    ) -> dict | None:
        if not comanda_id or not ticket_text:
            return None
        try:
            current = self.ticket_historial_repo.list_by_comanda(comanda_id)
            next_version = (max([int(r.get("version") or 0) for r in current]) + 1) if current else 1
            return self.ticket_historial_repo.create(
                comanda_id=comanda_id,
                version=next_version,
                tipo=tipo,
                ticket_text=ticket_text,
                created_by=created_by,
            )
        except Exception as exc:
            if self._is_missing_table(exc, "ticket_historial"):
                if strict:
                    raise ValueError(
                        "Falta migración SQL para historial de tickets. Ejecuta `sql/comandas_pagos_auditoria.sql`."
                    ) from exc
                return None
            raise

    def listar_tickets_historial(self, comanda_id: str) -> list[dict]:
        try:
            return self.ticket_historial_repo.list_by_comanda(comanda_id)
        except Exception as exc:
            if self._is_missing_table(exc, "ticket_historial"):
                return []
            raise

    def obtener_ticket_para_reimpresion(self, comanda_id: str, *, prefer: str = "LATEST") -> dict | None:
        rows = self.listar_tickets_historial(comanda_id)
        if not rows:
            return None
        mode = (prefer or "LATEST").strip().upper()
        if mode == "ORIGINAL":
            return rows[0]
        return rows[-1]

    def reimprimir_ticket(self, comanda_id: str, *, prefer: str = "LATEST") -> str:
        ticket_row = self.obtener_ticket_para_reimpresion(comanda_id, prefer=prefer)
        if ticket_row and ticket_row.get("ticket_text"):
            return str(ticket_row.get("ticket_text") or "")

        detail = self.get_comanda_detalle(comanda_id)
        com = detail.get("comanda") or {}
        items = detail.get("items") or []
        pagos = detail.get("pagos") or []
        propina_total = round(sum(float(p.get("propina") or 0) for p in pagos), 2)
        payload = {
            "negocio": "Barbacoa de Miranda",
            "folio": com.get("folio") or "N/A",
            "fecha_hora": com.get("created_at") or "",
            "mesa": com.get("mesa") or "",
            "mesero": com.get("mesero") or "",
            "metodo_pago": com.get("metodo_pago") or "",
            "propina": propina_total,
            "total": float(com.get("total") or 0),
            "items": items,
            "pagos": pagos,
        }
        return build_ticket_text(payload)

    def _regenerar_y_guardar_ticket(self, comanda_id: str, created_by: str = "SISTEMA") -> None:
        try:
            detail = self.get_comanda_detalle(comanda_id)
            com = detail.get("comanda") or {}
            items = detail.get("items") or []
            pagos = detail.get("pagos") or []
            propina_total = round(sum(float(p.get("propina") or 0) for p in pagos), 2)
            payload = {
                "negocio": "Barbacoa de Miranda",
                "folio": com.get("folio") or "N/A",
                "fecha_hora": com.get("created_at") or "",
                "mesa": com.get("mesa") or "",
                "mesero": com.get("mesero") or "",
                "metodo_pago": com.get("metodo_pago") or "",
                "propina": propina_total,
                "total": float(com.get("total") or 0),
                "items": items,
                "pagos": pagos,
            }
            ticket_text = build_ticket_text(payload)
            self.guardar_ticket_historial(
                comanda_id=comanda_id,
                ticket_text=ticket_text,
                tipo="CORREGIDO",
                created_by=created_by,
                strict=False
            )
        except Exception as e:
            self._logger.warning(f"Error regenerando ticket para comanda {comanda_id}: {e}")

    def _pagos_grouped(self, comanda_ids: list[str]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {cid: [] for cid in comanda_ids}
        if not comanda_ids:
            return grouped
        try:
            pagos = self.pagos_repo.list_by_comandas(comanda_ids)
        except Exception as exc:
            if self._is_missing_table(exc, "comanda_pagos"):
                return grouped
            raise
        for pago in pagos:
            cid = str(pago.get("comanda_id") or "")
            if not cid:
                continue
            grouped.setdefault(cid, []).append(pago)
        return grouped

    @staticmethod
    def _is_missing_table(exc: Exception, table_name: str) -> bool:
        msg = str(exc).lower()
        table_token = str(table_name or "").lower()
        return table_token in msg and (
            "does not exist" in msg or "relation" in msg or "schema cache" in msg or "column" in msg
        )

    def _is_missing_comanda_auditoria(self, exc: Exception) -> bool:
        cols = ("cancelada_at", "cancelada_por", "cancelacion_motivo", "status", "mesa")
        msg = str(exc).lower()
        for col in cols:
            if col in msg and ("column" in msg or "schema cache" in msg):
                return True
        return self._is_missing_table(exc, "comanda_correcciones")

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
        except Exception as exc:
            if not self._should_enqueue_offline(exc):
                raise
            self.offline.enqueue(GastoOperation(gasto.to_record()))
            return {"offline": True}

    def actualizar_gasto(
        self,
        gasto_id: str,
        *,
        concepto: str | None = None,
        categoria: str | None = None,
        monto: float | None = None,
        metodo_pago: str | None = None,
    ) -> dict:
        gasto_id = str(gasto_id or "").strip()
        if not gasto_id:
            raise ValueError("gasto_id es obligatorio")

        changes: dict = {}
        if concepto is not None:
            if not str(concepto).strip():
                raise ValueError("concepto no puede estar vacío")
            changes["concepto"] = str(concepto).strip()
        if categoria is not None:
            if not str(categoria).strip():
                raise ValueError("categoria no puede estar vacía")
            changes["categoria"] = str(categoria).strip()
        if monto is not None:
            if float(monto) <= 0:
                raise ValueError("monto debe ser > 0")
            changes["monto"] = round(float(monto), 2)
        if metodo_pago is not None:
            metodo = MetodoPago.from_raw(metodo_pago)
            changes["metodo_pago"] = metodo.value

        if not changes:
            raise ValueError("No hay cambios para actualizar.")

        # Updated field to force ordering/auditing
        changes["created_at"] = datetime.now(timezone.utc).isoformat()
        
        try:
            return self.gastos_repo.update_fields(gasto_id, changes)
        except Exception as exc:
            raise ValueError(f"No se pudo actualizar el gasto: {exc}")

    def eliminar_gasto(self, gasto_id: str) -> None:
        gasto_id = str(gasto_id or "").strip()
        if not gasto_id:
            raise ValueError("gasto_id es obligatorio")
        try:
            self.gastos_repo.delete(gasto_id)
        except Exception as exc:
            raise ValueError(f"No se pudo eliminar el gasto: {exc}")

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
        except Exception as exc:
            if not self._should_enqueue_offline(exc):
                raise
            self.offline.enqueue(PropinaOperation(propina.to_record()))
            return {"offline": True}

    def listar_propinas_rango(self, desde: datetime, hasta: datetime) -> list[dict]:
        if not isinstance(desde, datetime) or not isinstance(hasta, datetime):
            raise ValueError("desde y hasta deben ser datetime")
        if hasta < desde:
            raise ValueError("hasta debe ser >= desde")
        return self.propinas_repo.list_by_range(desde.isoformat(), hasta.isoformat())

    def listar_propinas_dia_detalle(self, fecha: date) -> list[dict]:
        if not isinstance(fecha, date):
            raise ValueError("fecha debe ser date")
        desde, hasta = self._day_range(fecha)
        rows = self.propinas_repo.list_by_range(desde, hasta)
        rows.sort(key=lambda r: str(r.get("fecha") or ""), reverse=True)
        return rows

    def actualizar_propina(
        self,
        propina_id: str,
        *,
        monto: float,
        mesero_id: str | None = None,
        mesero_nombre_snapshot: str | None = None,
        fuente: str = "NO_ESPECIFICADO",
    ) -> dict:
        propina_id = str(propina_id or "").strip()
        if not propina_id:
            raise ValueError("propina_id es obligatorio")

        existente = self.propinas_repo.get_by_id(propina_id)
        if not existente:
            raise ValueError("No existe la propina seleccionada.")

        propina = Propina.from_inputs(
            monto=monto,
            mesero_id=mesero_id,
            mesero_nombre_snapshot=mesero_nombre_snapshot,
            fuente=fuente,
            comanda_id=existente.get("comanda_id"),
        )
        payload = propina.to_record()
        # fecha de actualización para ordenar y auditar cambios.
        payload["fecha"] = datetime.now(timezone.utc).isoformat()
        res = self.propinas_repo.update_fields(propina_id, payload)
        
        comanda_id = existente.get("comanda_id")
        if comanda_id:
            try:
                pagos = self.pagos_repo.list_by_comanda(comanda_id)
                if pagos:
                    target_pago = next((p for p in pagos if str(p.get("metodo_pago")).strip().upper() == fuente), pagos[0])
                    self.pagos_repo.update_fields(target_pago["id"], {"propina": monto})
                self._regenerar_y_guardar_ticket(comanda_id)
            except Exception as e:
                self._logger.warning(f"Error sincronizando propina actualizada a comanda_pagos: {e}")
                
        return res

    def eliminar_propina(self, propina_id: str) -> None:
        propina_id = str(propina_id or "").strip()
        if not propina_id:
            raise ValueError("propina_id es obligatorio")
        existente = self.propinas_repo.get_by_id(propina_id)
        if not existente:
            raise ValueError("No existe la propina seleccionada.")
            
        comanda_id = existente.get("comanda_id")
        fuente = str(existente.get("fuente") or "").strip().upper()
        
        self.propinas_repo.delete(propina_id)

        if comanda_id:
            try:
                pagos = self.pagos_repo.list_by_comanda(comanda_id)
                if pagos:
                    target_pago = next((p for p in pagos if str(p.get("metodo_pago")).strip().upper() == fuente), pagos[0])
                    self.pagos_repo.update_fields(target_pago["id"], {"propina": 0.0})
                self._regenerar_y_guardar_ticket(comanda_id)
            except Exception as e:
                self._logger.warning(f"Error sincronizando propina eliminada a comanda_pagos: {e}")

    def _aggregate_propinas_rows(self, rows: list[dict]) -> list[dict]:
        agg: dict[str, dict] = {}
        for r in rows:
            mesero_id = r.get("mesero_id")
            mesero_name = (r.get("mesero_nombre_snapshot") or "").strip() or None
            # Agrupar por nombre cuando existe para evitar duplicados entre
            # registros de comanda (con id) y registros manuales (sin id).
            if mesero_name:
                key = f"NAME::{mesero_name.lower()}"
                label = mesero_name
            else:
                key = f"ID::{mesero_id}" if mesero_id else "SIN_NOMBRE"
                label = mesero_id or "Sin nombre"
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
                    "total_efectivo": 0.0,
                    "num_transfer": 0,
                    "total_transfer": 0.0,
                    "num_no_especificado": 0,
                }

            agg[key]["total_propinas"] += monto
            agg[key]["num_propinas"] += 1
            if fuente == "TARJETA":
                agg[key]["num_tarjeta"] += 1
                agg[key]["total_tarjeta"] += monto
            elif fuente == "EFECTIVO":
                agg[key]["num_efectivo"] += 1
                agg[key]["total_efectivo"] += monto
            elif fuente == "TRANSFER":
                agg[key]["num_transfer"] += 1
                agg[key]["total_transfer"] += monto
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

    # ---------------- Ventas por método ----------------
    def resumen_ventas_por_metodo_dia(self, fecha: date) -> dict:
        desde, hasta = self._day_range(fecha)
        return self._ventas_por_metodo_iso(desde, hasta)

    def resumen_ventas_por_metodo_rango(self, fecha_inicio: date, fecha_fin: date) -> dict:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")
        desde, _ = self._day_range(fecha_inicio)
        _, hasta = self._day_range(fecha_fin)
        return self._ventas_por_metodo_iso(desde, hasta)

    def _ventas_por_metodo_iso(self, desde_iso: str, hasta_iso: str) -> dict:
        resumen = {"EFECTIVO": 0.0, "TARJETA": 0.0, "TRANSFER": 0.0, "total": 0.0}

        try:
            rows = (
                self.client.table("comandas")
                .select("id, total, metodo_pago, status")
                .gte("created_at", desde_iso)
                .lte("created_at", hasta_iso)
                .neq("status", "CANCELADA")
                .execute()
            ).data or []
        except Exception as exc:
            if self._is_missing_comanda_auditoria(exc):
                rows = (
                    self.client.table("comandas")
                    .select("id, total, metodo_pago")
                    .gte("created_at", desde_iso)
                    .lte("created_at", hasta_iso)
                    .execute()
                ).data or []
            else:
                raise

        active_rows: list[dict] = []
        for row in rows:
            if str(row.get("status") or "").upper() == "CANCELADA":
                continue
            active_rows.append(row)
        if not active_rows:
            return resumen

        comanda_ids = [str(r.get("id") or "") for r in active_rows if r.get("id")]
        pagos_by_comanda = self._pagos_grouped(comanda_ids)

        for row in active_rows:
            total = round(float(row.get("total") or 0), 2)
            resumen["total"] += total
            cid = str(row.get("id") or "")
            pagos = pagos_by_comanda.get(cid) or []
            if pagos:
                for pago in pagos:
                    metodo = str(pago.get("metodo_pago") or "").strip().upper()
                    monto = round(float(pago.get("monto") or 0), 2)
                    if metodo in {"EFECTIVO", "TARJETA", "TRANSFER"}:
                        resumen[metodo] += monto
                continue
            metodo = str(row.get("metodo_pago") or "").strip().upper()
            if metodo in {"EFECTIVO", "TARJETA", "TRANSFER"}:
                resumen[metodo] += total

        for key in ("EFECTIVO", "TARJETA", "TRANSFER", "total"):
            resumen[key] = round(float(resumen[key]), 2)
        return resumen

    # ---------------- Cierre de caja ----------------
    def obtener_cierre(self, fecha: date) -> dict | None:
        return self.cierres_repo.get_by_fecha(fecha.isoformat())

    def crear_cierre(self, fecha: date, efectivo_reportado: float, notas: str | None = None) -> dict:
        if efectivo_reportado is None or float(efectivo_reportado) < 0:
            raise ValueError("efectivo_reportado debe ser >= 0")

        existente = self.obtener_cierre(fecha)
        if existente:
            raise ValueError(f"Ya existe un cierre para la fecha {fecha.isoformat()}")

        resumen_ventas = self.resumen_ventas_por_metodo_dia(fecha)
        total_ventas = float(resumen_ventas.get("total") or 0)
        ventas_efectivo = float(resumen_ventas.get("EFECTIVO") or 0)

        desde, hasta = self._day_range(fecha)
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
        except Exception as exc:
            if not self._should_enqueue_offline(exc):
                raise
            self.offline.enqueue(CierreOperation(cierre.to_record()))
            return {"offline": True}

    # ---------------- Offline sync ----------------
    def _archive_dropped_offline_op(self, record) -> None:
        path = os.path.join(self._base_dir, "data", "offline_dead_letter.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "dropped_at": datetime.now(timezone.utc).isoformat(),
            "id": record.record_id,
            "created_at": record.created_at,
            "op": record.operation.record_op(),
            "payload": record.operation.payload,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def sync_offline(self) -> int:
        synced = 0
        for record in self.offline.list_ops():
            try:
                record.operation.apply(self)
            except Exception as exc:
                if not self._should_enqueue_offline(exc):
                    try:
                        self._archive_dropped_offline_op(record)
                    except Exception:
                        self._logger.warning(
                            "offline op archive failed id=%s op=%s",
                            record.record_id,
                            record.operation.record_op(),
                            exc_info=True,
                        )
                    self.offline.delete_op(record.record_id)
                    self._logger.error(
                        "offline op dropped (non-transient) id=%s op=%s err=%s",
                        record.record_id,
                        record.operation.record_op(),
                        exc,
                    )
                    continue
                self._logger.warning(
                    "offline sync failed id=%s op=%s",
                    record.record_id,
                    record.operation.record_op(),
                    exc_info=True,
                )
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
            mesa=payload.get("mesa", ""),
            metodo_pago=payload.get("metodo_pago", MetodoPago.EFECTIVO.value),
            total=payload.get("total", 0),
            recibido=payload.get("recibido"),
            cambio=payload.get("cambio"),
            items=payload.get("items", []),
            propina=payload.get("propina"),
            pagos=payload.get("pagos", []),
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

    # ---------------------------------------------------------
    # INVENTARIO
    # ---------------------------------------------------------

    def listar_insumos(self) -> list[Insumo]:
        return self.insumos_repo.list_all()

    def crear_insumo(self, nombre: str, unidad: str, stock_minimo: float = 0.0) -> Insumo:
        insumo = Insumo(
            id=None,
            nombre=nombre,
            unidad=unidad,
            stock_actual=0.0,
            stock_minimo=stock_minimo,
            activo=True
        )
        created = self.insumos_repo.create(insumo)
        return Insumo.from_record(created)

    def actualizar_insumo(self, insumo_id: str, changes: dict) -> dict:
        return self.insumos_repo.update_fields(insumo_id, changes)

    def eliminar_insumo(self, insumo_id: str) -> None:
        self.insumos_repo.delete(insumo_id)

    def obtener_recetas_producto(self, producto_id: int) -> list[Receta]:
        return self.recetas_repo.list_by_producto(producto_id)

    def guardar_recetas_producto(self, producto_id: int, recetas_data: list[dict]) -> None:
        recetas = [Receta.from_record(r) for r in recetas_data]
        self.recetas_repo.replace_for_producto(producto_id, recetas)

    def ajustar_stock_insumo(
        self, insumo_id: str, current_stock: float, amount_to_add: float, descripcion: str, referencia_id: str | None = None
    ) -> None:
        new_stock = current_stock + amount_to_add
        if new_stock < 0:
            new_stock = 0.0

        tipo = "ENTRADA" if amount_to_add >= 0 else "SALIDA"
        
        self.insumos_repo.update_fields(insumo_id, {"stock_actual": new_stock})
        
        mov = MovimientoInventario(
            id=None,
            insumo_id=insumo_id,
            tipo=tipo,
            cantidad=abs(amount_to_add),
            motivo=descripcion,
            referencia_id=referencia_id
        )
        self.movimientos_inv_repo.create(mov)

    def descontar_inventario_por_comanda(self, comanda_id: str, items_comanda: list[dict]) -> None:
        try:
            from domain.inventario import calc_consumo
        except ImportError:
            self._logger.error("No se pudo importar calc_consumo para descontar inventario.")
            return

        recetas_records = [r.to_record() for r in self.recetas_repo.list_all()]
        consumos = calc_consumo(items_comanda, recetas_records)
        if not consumos:
            return

        insumos_activos = {i.id: i for i in self.listar_insumos() if i.id}

        for insumo_id, req_qty in consumos.items():
            insumo = insumos_activos.get(insumo_id)
            if not insumo:
                continue

            new_stock = insumo.stock_actual - req_qty
            if new_stock < 0:
                new_stock = 0.0

            self.insumos_repo.update_fields(insumo_id, {"stock_actual": new_stock})
            
            mov = MovimientoInventario(
                id=None,
                insumo_id=insumo_id,
                tipo="SALIDA",
                cantidad=req_qty,
                motivo="COMANDA",
                referencia_id=comanda_id
            )
            self.movimientos_inv_repo.create(mov)

    def obtener_alertas_stock(self) -> list[Insumo]:
        try:
            from domain.inventario import get_alertas_stock
            insumos_records = [i.to_record() for i in self.listar_insumos()]
            alertas = get_alertas_stock(insumos_records)
            return [Insumo.from_record(a) for a in alertas]
        except Exception as e:
            self._logger.error(f"Error al obtener alertas de stock: {e}")
            return []
