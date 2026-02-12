from __future__ import annotations

from datetime import date, timedelta, datetime
import csv
import os
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel
from services.reportes_service import (
    get_top_productos,
    get_ventas_por_dia,
    get_ventas_por_metodo,
    get_ventas_por_mesero,
)
from services.supabase_service import SupabaseService
from ui.reportes_graficas import ReportesGraficas


class ReportesView(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Reportes")
        self.geometry("1160x760")
        self.minsize(1040, 680)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self._top_productos = []
        self._ventas_por_dia = []
        self._ventas_por_metodo = {}
        self._ventas_por_mesero = []

        hoy = date.today()
        self.fecha_fin_var = tk.StringVar(value=hoy.isoformat())
        self.fecha_inicio_var = tk.StringVar(value=(hoy - timedelta(days=6)).isoformat())
        self.status_var = tk.StringVar(value="")

        self.ventas_efectivo_var = tk.StringVar(value="0.00")
        self.ventas_tarjeta_var = tk.StringVar(value="0.00")
        self.ventas_transfer_var = tk.StringVar(value="0.00")
        self.ventas_total_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._load_reportes()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")

        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 8), pady=10)
        ctk.CTkLabel(header, text="REPORTES", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=6, pady=10)

        filters = ctk.CTkFrame(self)
        filters.pack(fill="x", padx=12, pady=(12, 8))
        for col in range(9):
            filters.grid_columnconfigure(col, weight=(1 if col in {1, 3, 8} else 0))
        ctk.CTkLabel(filters, text="Inicio:").grid(row=0, column=0, padx=(8, 6), pady=8, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.fecha_inicio_var, width=140).grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        ctk.CTkLabel(filters, text="Fin:").grid(row=0, column=2, padx=(12, 6), pady=8, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.fecha_fin_var, width=140).grid(row=0, column=3, padx=6, pady=8, sticky="ew")
        ttk.Button(filters, text="Cargar", command=self._load_reportes).grid(row=0, column=4, padx=6, pady=8, sticky="ew")
        ttk.Button(filters, text="Exportar CSV", command=self._export_csv).grid(row=0, column=5, padx=6, pady=8, sticky="ew")
        ttk.Button(filters, text="Gráficas", command=self._open_graficas).grid(row=0, column=6, padx=6, pady=8, sticky="ew")

        resumen = ctk.CTkFrame(self)
        resumen.pack(fill="x", padx=12, pady=(0, 12))

        def _row(label: str, var: tk.StringVar, r: int):
            ctk.CTkLabel(resumen, text=label).grid(row=r, column=0, padx=6, pady=4, sticky="w")
            ctk.CTkLabel(resumen, textvariable=var, font=("Arial", 13, "bold")).grid(
                row=r, column=1, padx=6, pady=4, sticky="e"
            )

        _row("Ventas EFECTIVO:", self.ventas_efectivo_var, 0)
        _row("Ventas TARJETA:", self.ventas_tarjeta_var, 1)
        _row("Ventas TRANSFER:", self.ventas_transfer_var, 2)
        _row("Ventas TOTAL:", self.ventas_total_var, 3)
        resumen.grid_columnconfigure(1, weight=1)

        tables = ctk.CTkFrame(self)
        tables.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        tables.grid_columnconfigure(0, weight=1)
        tables.grid_columnconfigure(1, weight=1)
        tables.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(tables)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Top productos", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        top_frame = ctk.CTkFrame(left)
        top_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        top_frame.grid_rowconfigure(0, weight=1)
        top_frame.grid_columnconfigure(0, weight=1)
        self.top_tree = ttk.Treeview(top_frame, columns=("producto", "cantidad", "total"), show="headings", height=10)
        self.top_tree.heading("producto", text="Producto")
        self.top_tree.heading("cantidad", text="Cantidad")
        self.top_tree.heading("total", text="Total")
        self.top_tree.column("producto", width=320, anchor="w")
        self.top_tree.column("cantidad", width=80, anchor="center")
        self.top_tree.column("total", width=100, anchor="e")
        self.top_tree.grid(row=0, column=0, sticky="nsew")
        top_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.top_tree.yview)
        top_scroll.grid(row=0, column=1, sticky="ns")
        self.top_tree.configure(yscrollcommand=top_scroll.set)
        bind_mousewheel(self.top_tree, self.top_tree.yview)

        right = ctk.CTkFrame(tables)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Ventas por día", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        dia_frame = ctk.CTkFrame(right)
        dia_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        dia_frame.grid_rowconfigure(0, weight=1)
        dia_frame.grid_columnconfigure(0, weight=1)
        self.dia_tree = ttk.Treeview(dia_frame, columns=("fecha", "total"), show="headings", height=10)
        self.dia_tree.heading("fecha", text="Fecha")
        self.dia_tree.heading("total", text="Total")
        self.dia_tree.column("fecha", width=140, anchor="center")
        self.dia_tree.column("total", width=120, anchor="e")
        self.dia_tree.grid(row=0, column=0, sticky="nsew")
        dia_scroll = ttk.Scrollbar(dia_frame, orient="vertical", command=self.dia_tree.yview)
        dia_scroll.grid(row=0, column=1, sticky="ns")
        self.dia_tree.configure(yscrollcommand=dia_scroll.set)
        bind_mousewheel(self.dia_tree, self.dia_tree.yview)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=6)


    def _parse_fecha(self, value: str) -> date | None:
        try:
            return date.fromisoformat(value.strip())
        except Exception:
            return None

    def _load_reportes(self):
        inicio = self._parse_fecha(self.fecha_inicio_var.get())
        fin = self._parse_fecha(self.fecha_fin_var.get())
        if not inicio or not fin:
            messagebox.showwarning("Fechas inválidas", "Usa el formato YYYY-MM-DD.")
            return
        if fin < inicio:
            messagebox.showwarning("Rango inválido", "La fecha fin debe ser >= fecha inicio.")
            return

        self.status_var.set("Cargando reportes...")
        self.update_idletasks()

        try:
            self._top_productos = get_top_productos(inicio, fin, limit=10, db=self.db)
            self._ventas_por_dia = get_ventas_por_dia(inicio, fin, db=self.db)
            self._ventas_por_metodo = get_ventas_por_metodo(inicio, fin, db=self.db)
            self._ventas_por_mesero = get_ventas_por_mesero(inicio, fin, limit=8, db=self.db)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("Error", f"No se pudieron cargar los reportes:\n{e}")
            return

        self._render_tablas()
        self.status_var.set("Reportes listos.")

    def _render_tablas(self):
        for row in self.top_tree.get_children():
            self.top_tree.delete(row)
        for r in self._top_productos:
            self.top_tree.insert(
                "",
                "end",
                values=(r.get("producto"), r.get("cantidad_total"), f"${float(r.get('subtotal_total') or 0):.2f}"),
            )

        for row in self.dia_tree.get_children():
            self.dia_tree.delete(row)
        for r in self._ventas_por_dia:
            self.dia_tree.insert("", "end", values=(r.get("fecha"), f"${float(r.get('total') or 0):.2f}"))

        self.ventas_efectivo_var.set(f"${float(self._ventas_por_metodo.get('EFECTIVO') or 0):.2f}")
        self.ventas_tarjeta_var.set(f"${float(self._ventas_por_metodo.get('TARJETA') or 0):.2f}")
        self.ventas_transfer_var.set(f"${float(self._ventas_por_metodo.get('TRANSFER') or 0):.2f}")
        self.ventas_total_var.set(f"${float(self._ventas_por_metodo.get('total') or 0):.2f}")

    def _export_csv(self):
        if not self._top_productos and not self._ventas_por_dia:
            messagebox.showwarning("Sin datos", "No hay reportes cargados para exportar.")
            return

        exports_dir = "exports"
        os.makedirs(exports_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(exports_dir, f"reporte_{stamp}.csv")

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Reporte de ventas"])
                w.writerow(["Fecha inicio", self.fecha_inicio_var.get().strip()])
                w.writerow(["Fecha fin", self.fecha_fin_var.get().strip()])
                w.writerow([])

                w.writerow(["Ventas por método"])
                w.writerow(["EFECTIVO", self._ventas_por_metodo.get("EFECTIVO", 0)])
                w.writerow(["TARJETA", self._ventas_por_metodo.get("TARJETA", 0)])
                w.writerow(["TRANSFER", self._ventas_por_metodo.get("TRANSFER", 0)])
                w.writerow(["TOTAL", self._ventas_por_metodo.get("total", 0)])
                w.writerow([])

                w.writerow(["Top productos"])
                w.writerow(["Producto", "Cantidad", "Total"])
                for r in self._top_productos:
                    w.writerow([r.get("producto"), r.get("cantidad_total"), r.get("subtotal_total")])
                w.writerow([])

                w.writerow(["Ventas por día"])
                w.writerow(["Fecha", "Total"])
                for r in self._ventas_por_dia:
                    w.writerow([r.get("fecha"), r.get("total")])

            messagebox.showinfo("OK", f"CSV exportado en {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar CSV:\n{e}")

    def _open_graficas(self):
        inicio = self._parse_fecha(self.fecha_inicio_var.get())
        fin = self._parse_fecha(self.fecha_fin_var.get())
        if not inicio or not fin:
            messagebox.showwarning("Fechas inválidas", "Usa el formato YYYY-MM-DD.")
            return
        ReportesGraficas(
            self,
            inicio,
            fin,
            self._ventas_por_metodo,
            self._ventas_por_dia,
            self._ventas_por_mesero,
        )
