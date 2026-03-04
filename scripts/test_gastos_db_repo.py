import os
import sys

# Ensure correct path to import Barbacoa modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from services.supabase_service import SupabaseService
from domain.models import MetodoPago

def main():
    db = SupabaseService()
    
    print("1. Creating dummy expense...")
    result = db.crear_gasto(
        concepto="Gasto de Prueba Automatizada",
        categoria="GENERAL",
        monto=50.0,
        metodo_pago=MetodoPago.EFECTIVO.value
    )
    
    gasto_id = result.get("id")
    if not gasto_id:
        print("Failed to create expense.")
        return
    print(f"Created expense ID: {gasto_id}")
    
    print("\n2. Updating expense...")
    db.actualizar_gasto(
        gasto_id=gasto_id,
        concepto="Gasto de Prueba Actualizado",
        monto=75.50
    )
    print("Expense updated successfully.")
    
    print("\n3. Deleting expense...")
    db.eliminar_gasto(gasto_id)
    print("Expense deleted successfully.")
    
    print("\nSuccess! All operations completed without errors.")

if __name__ == "__main__":
    main()
