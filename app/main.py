import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.comanda_view import ComandaView

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class POS(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Barbacoa POS - Nivel Restaurante")
        self.geometry("1100x700")

        self.db = SupabaseService()

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        tab_comandas = self.tabs.add("Comandas")
        ComandaView(tab_comandas, self.db).pack(fill="both", expand=True)


if __name__ == "__main__":
    app = POS()
    app.mainloop()
