from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo

class PropinasDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Control de Propinas")
        self.geometry("850x650")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.menu_color = "#34495e"
        self.mesero_map = {} # Mapa nombre -> id

        # Variables
        self.monto_var = tk.StringVar()
        self.mesero_var = tk.StringVar(value="Seleccionar...")
        
        today = date.today()
        self.year_var = tk.StringVar(value=str(today.year))
        self.month_var = tk.StringVar(value=str(today.month))

        self._build_ui()
        self._load_meseros()
        self._load_reporte()

    def _build_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(15, 10), pady=10)
        
        ctk.CTkLabel(header, text="REGISTRO DE PROPINAS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", pady=10)

        # 2. PANEL DE REGISTRO
        reg_frame = ctk.CTkFrame(self)
        reg_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(reg_frame, text="Registrar Nueva Propina", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        form_inner = ctk.CTkFrame(reg_frame, fg_color="transparent")
        form_inner.pack(fill="x", padx=5, pady=(0, 15))

        # Labels
        ctk.CTkLabel(form_inner, text="Mesero", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, sticky="w")
        ctk.CTkLabel(form_inner, text="Monto ($)", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=10, sticky="w")

        # Inputs
        self.menu_mesero = ctk.CTkOptionMenu(form_inner, values=["Cargando..."], variable=self.mesero_var, width=250, height=35,
                                             fg_color=self.menu_color, button_color=self.menu_color, button_hover_color="#2c3e50")
        self.menu_mesero.grid(row=1, column=0, padx=10, pady=(5,0))

        self.entry_monto = ctk.CTkEntry(form_inner, textvariable=self.monto_var, placeholder_text="0.00", width=150, height=35)
        self.entry_monto.grid(row=1, column=1, padx=10, pady=(5,0))

        # Botón Guardar
        ctk.CTkButton(form_inner, text="REGISTRAR", font=("Arial", 12, "bold"), 
                      fg_color="#27ae60", hover_color="#219a52", height=35, width=150,
                      command=self._guardar).grid(row=1, column=2, padx=20, pady=(5,0))

        # 3. REPORTE MENSUAL
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Filtros del reporte
        filter_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(filter_frame, text="REPORTE MENSUAL:", font=("Arial", 13, "bold")).pack(side="left", padx=(5, 10))
        
        # Selectores de fecha compactos
        ctk.CTkOptionMenu(filter_frame, values=["2024", "2025", "2026"], variable=self.year_var, width=80,
                          fg_color=self.menu_color, button_color=self.menu_color).pack(side="left", padx=5)
        
        meses = [str(i) for i in range(1, 13)]
        ctk.CTkOptionMenu(filter_frame, values=meses, variable=self.month_var, width=70,
                          fg_color=self.menu_color, button_color=self.menu_color).pack(side="left", padx=5)

        ctk.CTkButton(filter_frame, text="CONSULTAR", width=100, fg_color="#34495e", command=self._load_reporte).pack(side="left", padx=15)

        # Tabla
        cols = ("mesero", "total", "cantidad")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        
        self.tree.heading("mesero", text="Mesero")
        self.tree.heading("total", text="Total ($)")
        self.tree.heading("cantidad", text="# Propinas")
        
        self.tree.column("mesero", width=300)
        self.tree.column("total", width=150, anchor="e")
        self.tree.column("cantidad", width=100, anchor="center")

        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroller.pack(side="right", fill="y", padx=(0,10), pady=10)

    def _load_meseros(self):
        try:
            meseros_db = self.db.listar_meseros()
            active_names = []
            self.mesero_map = {}
            for m in meseros_db:
                if m.get("activo"):
                    name = m.get("nombre", "Sin Nombre")
                    mid = m.get("id")
                    active_names.append(name)
                    self.mesero_map[name] = mid
            
            if active_names:
                self.menu_mesero.configure(values=active_names)
                self.mesero_var.set(active_names[0])
            else:
                self.menu_mesero.configure(values=["No hay meseros activos"])
        except Exception as e:
            print(f"Error cargando meseros: {e}")

    def _guardar(self):
        mesero_name = self.mesero_var.get()
        monto_str = self.monto_var.get().strip()
        
        if mesero_name not in self.mesero_map:
            messagebox.showwarning("Error", "Selecciona un mesero valido.")
            return
            
        mesero_id = self.mesero_map[mesero_name]

        try:
            monto = float(monto_str)
            if monto <= 0: raise ValueError
        except:
            messagebox.showwarning("Monto", "Ingresa un monto valido mayor a 0.")
            return

        try:
            self.db.crear_propina(
                monto=monto,
                mesero_id=mesero_id,
                mesero_nombre_snapshot=mesero_name,
                fuente="MANUAL",
                comanda_id=None
            )
            self.monto_var.set("")
            self._load_reporte()
            messagebox.showinfo("Exito", f"Propina de ${monto:.2f} registrada para {mesero_name}.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _load_reporte(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            rows = self.db.reporte_propinas_mes(y, m)
            
            for r in rows:
                self.tree.insert("", "end", values=(
                    r.get("mesero") or "Desconocido",
                    f"${float(r.get('total_propinas') or 0):.2f}",
                    r.get("num_propinas")
                ))
        except Exception as e:
            print(f"Error reporte propinas: {e}")
