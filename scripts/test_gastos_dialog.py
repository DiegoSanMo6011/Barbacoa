import tkinter as tk
import os
import sys

# Ensure correct path to import Barbacoa modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from ui.gastos_dialog import GastosDialog
from services.supabase_service import SupabaseService

def main():
    root = tk.Tk()
    root.withdraw() # Hide root window
    
    # Init Supabase
    db = SupabaseService()
    
    # Show dialog
    dialog = GastosDialog(root, db)
    
    # Just run it
    root.mainloop()

if __name__ == "__main__":
    main()
