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
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="PROPINAS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        sec_a = ctk.CTkFrame(self)
        sec_a.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(sec_a, text="Registrar propina", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=4, padx=6, pady=(6, 10), sticky="w"
        )

        ctk.CTkLabel(sec_a, text="Monto:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(sec_a, textvariable=self.monto_var, width=120).grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(sec_a, text="Mesero:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        self.mesero_menu = ctk.CTkOptionMenu(
            sec_a,
            values=[],
            variable=self.mesero_var,
            command=self._on_mesero_selected,
        )
        self.mesero_menu.grid(row=1, column=3, padx=6, pady=6, sticky="w")


        ttk.Button(sec_a, text="Guardar", style="Accent.TButton", command=self._guardar_propina).grid(
            row=2, column=3, padx=6, pady=6, sticky="e"
        )

        # Section B: reporte mensual
        sec_b = ctk.CTkFrame(self)
        sec_b.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkLabel(sec_b, text="Reporte mensual", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=5, padx=6, pady=(10, 6), sticky="w"
        )

        ctk.CTkLabel(sec_b, text="Ano:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        years = [str(date.today().year - 1), str(date.today().year), str(date.today().year + 1)]
        self.year_menu = ctk.CTkOptionMenu(sec_b, values=years, variable=self.year_var)
        self.year_menu.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(sec_b, text="Mes:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        months = [str(m) for m in range(1, 13)]
        self.month_menu = ctk.CTkOptionMenu(sec_b, values=months, variable=self.month_var)
        self.month_menu.grid(row=1, column=3, padx=6, pady=6, sticky="w")

        ttk.Button(sec_b, text="Actualizar", command=self._load_reporte).grid(
            row=1, column=4, padx=6, pady=6, sticky="e"
        )

        table_frame = ctk.CTkFrame(sec_b)
        table_frame.grid(row=2, column=0, columnspan=5, padx=6, pady=8, sticky="nsew")
        sec_b.grid_rowconfigure(2, weight=1)
        sec_b.grid_columnconfigure(4, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("mesero", "total", "num"),
            show="headings",
            height=12,
        )
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
