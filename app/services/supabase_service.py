from supabase import create_client
from .settings import SUPABASE_URL, SUPABASE_KEY


class SupabaseService:
    def __init__(self):
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def get_productos(self):
        res = self.client.table("productos").select("*").eq("activo", True).order("categoria").execute()
        return res.data or []

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
