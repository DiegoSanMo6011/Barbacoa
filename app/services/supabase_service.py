from datetime import date, datetime, time, timezone
from supabase import create_client
from .settings import SUPABASE_URL, SUPABASE_KEY


class SupabaseService:
    def __init__(self):
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def get_productos(self):
        res = self.client.table("productos").select("*").eq("activo", True).order("categoria").execute()
        return res.data or []

    def listar_productos(self) -> list[dict]:
        res = self.client.table("productos").select("*").order("categoria").execute()
        return res.data or []

    def crear_producto(self, nombre: str, categoria: str, precio: float, activo: bool = True) -> dict:
        if not nombre or not nombre.strip():
            raise ValueError("nombre es obligatorio")
        if not categoria or not categoria.strip():
            raise ValueError("categoria es obligatoria")
        if precio is None or float(precio) < 0:
            raise ValueError("precio debe ser >= 0")
        data = {
            "nombre": nombre.strip(),
            "categoria": categoria.strip(),
            "precio": round(float(precio), 2),
            "activo": bool(activo),
        }
        res = self.client.table("productos").insert(data).execute()
        return res.data[0]

    def actualizar_producto(
        self,
        producto_id: int,
        nombre: str | None = None,
        categoria: str | None = None,
        precio: float | None = None,
        activo: bool | None = None,
    ) -> dict:
        if producto_id is None:
            raise ValueError("producto_id es obligatorio")
        data: dict = {}
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("nombre es obligatorio")
            data["nombre"] = nombre.strip()
        if categoria is not None:
            if not categoria.strip():
                raise ValueError("categoria es obligatoria")
            data["categoria"] = categoria.strip()
        if precio is not None:
            if float(precio) < 0:
                raise ValueError("precio debe ser >= 0")
            data["precio"] = round(float(precio), 2)
        if activo is not None:
            data["activo"] = bool(activo)
        if not data:
            raise ValueError("no hay cambios para actualizar")
        res = self.client.table("productos").update(data).eq("id", producto_id).execute()
        return res.data[0]

    def crear_comanda(self, mesero: str, metodo_pago: str, total: float, recibido: float | None, cambio: float | None):
        data = {
            "mesero": mesero,
            "metodo_pago": metodo_pago,
            "total": round(float(total), 2),
            "recibido": None if recibido is None else round(float(recibido), 2),
            "cambio": None if cambio is None else round(float(cambio), 2),
            "status": "PAGADA",
        }
        res = self.client.table("comandas").insert(data).execute()
        return res.data[0]

    def agregar_items(self, comanda_id: str, items: list[dict]):
        # items: {producto_id, nombre_snapshot, precio_unitario, cantidad, subtotal}
        payload = []
        for it in items:
            payload.append({
                "comanda_id": comanda_id,
                "producto_id": it["producto_id"],
                "nombre_snapshot": it["nombre_snapshot"],
                "precio_unitario": round(float(it["precio_unitario"]), 2),
                "cantidad": int(it["cantidad"]),
                "subtotal": round(float(it["subtotal"]), 2),
            })
        self.client.table("comanda_items").insert(payload).execute()

   # ---------------- Gastos ----------------
    def crear_gasto(self, concepto: str, categoria: str, monto: float, nota: str | None = None, metodo_pago: str = "EFECTIVO") -> dict:
        if not concepto or not concepto.strip():
            raise ValueError("concepto es obligatorio")
        if not categoria or not categoria.strip():
            raise ValueError("categoria es obligatoria")
        if not metodo_pago or not metodo_pago.strip(): 
            raise ValueError("metodo_pago es obligatorio")
        if monto is None or float(monto) <= 0:
            raise ValueError("monto debe ser > 0")

        data = {
            "concepto": concepto.strip(),
            "categoria": categoria.strip(),
            "monto": round(float(monto), 2),
            "nota": nota.strip() if isinstance(nota, str) and nota.strip() else None,
            "metodo_pago": metodo_pago.strip() # faltaba el metodo de pago
        }
        res = self.client.table("gastos").insert(data).execute()
        return res.data[0]

    # ---------------- Meseros ----------------
    def listar_meseros_activos(self) -> list[dict]:
        res = (
            self.client.table("meseros")
            .select("id, nombre, activo")
            .eq("activo", True)
            .order("nombre")
            .execute()
        )
        return res.data or []

    def listar_meseros(self) -> list[dict]:
        res = (
            self.client.table("meseros")
            .select("id, nombre, activo")
            .order("nombre")
            .execute()
        )
        return res.data or []

    def crear_mesero(self, nombre: str) -> dict:
        if not nombre or not nombre.strip():
            raise ValueError("nombre es obligatorio")
        data = {"nombre": nombre.strip(), "activo": True}
        res = self.client.table("meseros").insert(data).execute()
        return res.data[0]

    def actualizar_mesero(self, mesero_id: str, nombre: str | None = None, activo: bool | None = None) -> dict:
        if not mesero_id:
            raise ValueError("mesero_id es obligatorio")
        data: dict = {}
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("nombre es obligatorio")
            data["nombre"] = nombre.strip()
        if activo is not None:
            data["activo"] = bool(activo)
        if not data:
            raise ValueError("no hay cambios para actualizar")
        res = self.client.table("meseros").update(data).eq("id", mesero_id).execute()
        return res.data[0]

    def listar_gastos_dia(self, fecha: date) -> list[dict]:
        # Criterio: rango completo del día en UTC (00:00:00 -> 23:59:59.999999)
        desde, hasta = self._day_range(fecha)
        res = (
            self.client.table("gastos")
            .select("*")
            .gte("created_at", desde)
            .lte("created_at", hasta)
            .order("created_at")
            .execute()
        )
        return res.data or []

    # ---------------- Propinas ----------------
    def crear_propina(
        self,
        monto: float,
        mesero_id: str | None = None,
        mesero_nombre_snapshot: str | None = None,
        fuente: str = "MANUAL",
        comanda_id: str | None = None,
    ) -> dict:
        if monto is None or float(monto) < 0:
            raise ValueError("monto debe ser >= 0")
        if mesero_nombre_snapshot is not None and not mesero_nombre_snapshot.strip():
            mesero_nombre_snapshot = None
        if fuente is None or not str(fuente).strip():
            fuente = "MANUAL"

        data = {
            "monto": round(float(monto), 2),
            "mesero_id": mesero_id,
            "mesero_nombre_snapshot": mesero_nombre_snapshot.strip() if mesero_nombre_snapshot else None,
            "fuente": fuente.strip(),
            "comanda_id": comanda_id,
        }
        res = self.client.table("propinas").insert(data).execute()
        return res.data[0]

    def listar_propinas_rango(self, desde: datetime, hasta: datetime) -> list[dict]:
        if not isinstance(desde, datetime) or not isinstance(hasta, datetime):
            raise ValueError("desde y hasta deben ser datetime")
        if hasta < desde:
            raise ValueError("hasta debe ser >= desde")

        res = (
            self.client.table("propinas")
            .select("*")
            .gte("fecha", desde.isoformat())
            .lte("fecha", hasta.isoformat())
            .order("fecha")
            .execute()
        )
        return res.data or []

    def reporte_propinas_mes(self, year: int, month: int) -> list[dict]:
        if month < 1 or month > 12:
            raise ValueError("month debe estar entre 1 y 12")

        desde = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            hasta = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            hasta = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        # Usamos rango [desde, hasta) con ajuste al criterio de lte
        hasta = hasta.replace(microsecond=0) - datetime.resolution

        rows = self.listar_propinas_rango(desde, hasta)
        agg: dict[str, dict] = {}

        for r in rows:
            mesero_id = r.get("mesero_id")
            mesero_name = r.get("mesero_nombre_snapshot") or None
            key = mesero_id or mesero_name or "SIN_NOMBRE"
            label = mesero_name or mesero_id or "Sin nombre"

            if key not in agg:
                agg[key] = {"mesero": label, "total_propinas": 0.0, "num_propinas": 0}

            agg[key]["total_propinas"] += float(r.get("monto") or 0)
            agg[key]["num_propinas"] += 1

        result = list(agg.values())
        result.sort(key=lambda x: (-x["total_propinas"], x["mesero"]))
        return result

    # ---------------- Cierre de caja ----------------
    def obtener_cierre(self, fecha: date) -> dict | None:
        res = self.client.table("cierres_caja").select("*").eq("fecha", fecha.isoformat()).execute()
        if not res.data:
            return None
        return res.data[0]

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
            float(r.get("total") or 0)
            for r in ventas_rows
            if r.get("metodo_pago") == "EFECTIVO"
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

        data = {
            "fecha": fecha.isoformat(),
            "total_ventas": round(float(total_ventas), 2),
            "total_gastos": round(float(total_gastos), 2),
            "neto": round(float(neto), 2),
            "efectivo_reportado": round(float(efectivo_reportado), 2),
            "diferencia_efectivo": round(float(diferencia_efectivo), 2),
            "notas": notas.strip() if isinstance(notas, str) and notas.strip() else None,
        }
        res = self.client.table("cierres_caja").insert(data).execute()
        return res.data[0]

    # ---------------- Helpers ----------------
    def _day_range(self, fecha: date) -> tuple[str, str]:
        # Rango en UTC para created_at: 00:00:00 -> 23:59:59.999999
        start = datetime.combine(fecha, time.min, tzinfo=timezone.utc)
        end = datetime.combine(fecha, time.max, tzinfo=timezone.utc)
        return start.isoformat(), end.isoformat()
