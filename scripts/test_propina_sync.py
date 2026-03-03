import os
import sys

# Add app folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from services.supabase_service import SupabaseService

def test_sync():
    """
    To verify this, we will run the command against a real or mocked Supabase instance.
    Since we don't have tests/mock_context configured to run, we'll try to execute it as if running against the real db. 
    However, inserting a real comanda into production requires care. 
    We will just write a script that does it explicitly if possible, or wait to run the UI.
    """
    svc = SupabaseService()
    print("Supabase connected.")
    
    # 1. Crear producto de prueba
    print("Creando producto de prueba...")
    prod = svc.crear_producto("TEST_PROD_SYNC", "TEST", 10.0, activo=False)
    
    # 2. Crear comanda
    print("Creando comanda de prueba...")
    comanda = svc.guardar_comanda(
        mesero="SISTEMA",
        mesa="TEST_MESA",
        metodo_pago="TARJETA",
        total=10.0,
        recibido=10.0,
        cambio=0.0,
        items=[{"producto_id": prod["id"], "nombre": "TEST_PROD_SYNC", "cantidad": 1, "precio": 10.0}],
        pagos=[{"metodo_pago": "TARJETA", "monto": 10.0, "propina": 2.0}]
    )
    comanda_id = comanda["id"]
    print(f"Comanda ID: {comanda_id}")
    
    detalle = svc.get_comanda_detalle(comanda_id)
    print("Comanda pagos creados:", [p.get("propina") for p in detalle["pagos"]])
    
    # Get the propina
    propinas = svc.client.table("propinas").select("*").eq("comanda_id", comanda_id).execute().data
    print("Propinas insertadas:", propinas)
    
    if not propinas:
        print("No se creo propina.")
        return
        
    propina_id = propinas[0]["id"]
    
    # 3. Actualizar propina
    print("Actualizando propina a 5.0...")
    svc.actualizar_propina(propina_id, monto=5.0, mesero_nombre_snapshot="SISTEMA", fuente="TARJETA")
    
    detalle_actualizado = svc.get_comanda_detalle(comanda_id)
    print("Comanda pagos despues de actualizar tip:", [p.get("propina") for p in detalle_actualizado["pagos"]])
    
    ticket_after = svc.reimprimir_ticket(comanda_id)
    print("Ticket tras actualización (sección):")
    for line in ticket_after.split("\n"):
        if "Propina" in line or "Total a pagar" in line:
            print(line)
    
    # 4. Eliminar propina
    print("Eliminando propina...")
    svc.eliminar_propina(propina_id)
    
    detalle_eliminado = svc.get_comanda_detalle(comanda_id)
    print("Comanda pagos despues de eliminar tip:", [p.get("propina") for p in detalle_eliminado["pagos"]])
    
    ticket_deleted = svc.reimprimir_ticket(comanda_id)
    print("Ticket tras eliminación (sección):")
    for line in ticket_deleted.split("\n"):
        if "Propina" in line or "Total a pagar" in line:
            print(line)
    
    # Clean up
    print("Limpiando...")
    svc.client.table("comanda_pagos").delete().eq("comanda_id", comanda_id).execute()
    svc.client.table("comanda_items").delete().eq("comanda_id", comanda_id).execute()
    svc.client.table("comandas").delete().eq("id", comanda_id).execute()
    svc.productos_repo.update_fields(prod["id"], {"activo": False})
    
    print("Test completado.")

if __name__ == "__main__":
    test_sync()
