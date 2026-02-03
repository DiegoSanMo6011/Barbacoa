from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo

class PersonalDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Gestión de Personal")
        self.geometry("700x550")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.nombre_var = tk.StringVar()

        self._build_ui()
        self._load_meseros()

    def _build_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(15, 10), pady=10)
        
        ctk.CTkLabel(header, text="PERSONAL - MESEROS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", pady=10)

        # 2. FORMULARIO DE ALTA
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(form_frame, text="Nombre del Nuevo Mesero", font=("Arial", 12, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        input_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=15, pady=(0, 15))

        self.entry_nombre = ctk.CTkEntry(input_row, textvariable=self.nombre_var, placeholder_text="Ej: Juan Perez", height=35, font=("Arial", 14))
        self.entry_nombre.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Botón Verde Compacto
        ctk.CTkButton(input_row, text="AGREGAR", font=("Arial", 12, "bold"), 
                      fg_color="#27ae60", hover_color="#219a52", height=35, width=120,
                      command=self._crear_mesero).pack(side="right")

        # 3. LISTA DE PERSONAL
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ctk.CTkLabel(list_frame, text="LISTA DE PERSONAL ACTIVO", font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=10)

        cols = ("nombre", "estado")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("estado", text="Estado (Activo)")
        
        self.tree.column("nombre", width=400)
        self.tree.column("estado", width=150, anchor="center")

        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=(0,10))
        scroller.pack(side="right", fill="y", padx=(0,10), pady=(0,10))

        # Botón para cambiar estado (Secundario/Azul)
        btn_action = ctk.CTkFrame(self, fg_color="transparent")
        btn_action.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(btn_action, text="CAMBIAR ESTADO (ACTIVO/INACTIVO)", 
                      fg_color="#34495e", hover_color="#2c3e50", height=35,
                      command=self._toggle_activo).pack(fill="x")

    def _load_meseros(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            meseros = self.db.listar_meseros()
            for m in meseros:
                estado = "SI" if m.get("activo") else "NO"
                self.tree.insert("", "end", iid=m["id"], values=(m.get("nombre") or "", estado))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar personal:\n{e}")

    def _crear_mesero(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "Escribe el nombre del mesero.")
            return
        try:
            self.db.crear_mesero(nombre)
            self.nombre_var.set("")
            self._load_meseros()
            messagebox.showinfo("Exito", "Mesero agregado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear mesero:\n{e}")

    def _toggle_activo(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Seleccion", "Selecciona un mesero de la lista para cambiar su estado.")
            return
        mesero_id = sel[0]
        values = self.tree.item(mesero_id, "values")
        if not values: return
        
        activo_actual = values[1] == "SI"
        nuevo_estado = not activo_actual
        
        try:
            self.db.actualizar_mesero(mesero_id, activo=nuevo_estado)
            self._load_meseros()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar:\n{e}")
