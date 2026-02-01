from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo


class PersonalDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Personal - Meseros")
        self.geometry("760x520")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.nombre_var = tk.StringVar()

        self._build_ui()
        self._load_meseros()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="PERSONAL - MESEROS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(form, text="Nombre:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.nombre_var, width=220).grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ctk.CTkButton(form, text="Agregar", command=self._crear_mesero).grid(row=0, column=2, padx=6, pady=6, sticky="w")

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree = ttk.Treeview(table_frame, columns=("nombre", "activo"), show="headings", height=12)
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("activo", text="Activo")
        self.tree.column("nombre", width=360, anchor="w")
        self.tree.column("activo", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", self._toggle_activo)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Activar/Desactivar", command=self._toggle_activo).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Refrescar", command=self._load_meseros).pack(side="left", padx=6)

    def _load_meseros(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            meseros = self.db.listar_meseros()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar personal:\n{e}")
            return
        for m in meseros:
            activo = "SI" if m.get("activo") else "NO"
            self.tree.insert("", "end", iid=m["id"], values=(m.get("nombre") or "", activo))

    def _crear_mesero(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "Escribe el nombre del mesero.")
            return
        try:
            self.db.crear_mesero(nombre)
            self.nombre_var.set("")
            self._load_meseros()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear mesero:\n{e}")

    def _toggle_activo(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        mesero_id = sel[0]
        values = self.tree.item(mesero_id, "values")
        if not values:
            return
        activo_actual = values[1] == "SI"
        try:
            self.db.actualizar_mesero(mesero_id, activo=not activo_actual)
            self._load_meseros()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar mesero:\n{e}")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = PersonalDialog(root, db)
    dlg.mainloop()
