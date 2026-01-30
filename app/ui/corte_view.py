from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from domain.corte import calc_diferencia, calc_efectivo_teorico
from ui.assets import load_logo
from services.corte_service import (
    get_corte_por_fecha,
    get_gastos_total,
    get_propinas_total,
    get_ventas_por_metodo,
    save_corte,
)
from services.supabase_service import SupabaseService


class CorteView(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Corte")
        self.geometry("840x560")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self._last = {}

        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        self.efectivo_contado_var = tk.StringVar()
        self.diferencia_var = tk.StringVar(value="0.00")
        self.status_var = tk.StringVar(value="")

        self.total_ventas_var = tk.StringVar(value="0.00")
        self.ventas_efectivo_var = tk.StringVar(value="0.00")
        self.ventas_tarjeta_var = tk.StringVar(value="0.00")
        self.ventas_transfer_var = tk.StringVar(value="0.00")
        self.total_gastos_var = tk.StringVar(value="0.00")
        self.total_propinas_var = tk.StringVar(value="0.00")
        self.efectivo_teorico_var = tk.StringVar(value="0.00")
        self.neto_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="CORTE DEL DÍA", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        top_bar = ctk.CTkFrame(self)
        top_bar.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(top_bar, text="Resumen del día", font=("Arial", 14, "bold")).pack(side="left", padx=6)

        date_row = ctk.CTkFrame(top_bar, fg_color="transparent")
        date_row.pack(side="right")
        ctk.CTkLabel(date_row, text="Fecha (YYYY-MM-DD):").pack(side="left", padx=6)
        ctk.CTkEntry(date_row, textvariable=self.fecha_var, width=140).pack(side="left", padx=6)
        ctk.CTkButton(date_row, text="Cargar", command=self._refresh).pack(side="left", padx=6)

        resumen = ctk.CTkFrame(self)
        resumen.pack(fill="x", padx=12, pady=(0, 12))

        def _row(label: str, var: tk.StringVar, r: int):
            ctk.CTkLabel(resumen, text=label).grid(row=r, column=0, padx=6, pady=4, sticky="w")
            ctk.CTkLabel(resumen, textvariable=var, font=("Arial", 13, "bold")).grid(
                row=r, column=1, padx=6, pady=4, sticky="e"
            )

        _row("Total ventas:", self.total_ventas_var, 0)
        _row("Ventas EFECTIVO:", self.ventas_efectivo_var, 1)
        _row("Ventas TARJETA:", self.ventas_tarjeta_var, 2)
        _row("Ventas TRANSFER:", self.ventas_transfer_var, 3)
        _row("Total gastos:", self.total_gastos_var, 4)
        _row("Total propinas:", self.total_propinas_var, 5)
        _row("Efectivo teórico:", self.efectivo_teorico_var, 6)
        _row("Neto:", self.neto_var, 7)

        resumen.grid_columnconfigure(1, weight=1)

        efectivo_frame = ctk.CTkFrame(self)
        efectivo_frame.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkLabel(efectivo_frame, text="Efectivo contado:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.efectivo_entry = ctk.CTkEntry(efectivo_frame, textvariable=self.efectivo_contado_var, width=140)
        self.efectivo_entry.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.efectivo_entry.bind("<KeyRelease>", lambda _e: self._update_diferencia())

        ctk.CTkLabel(efectivo_frame, text="Diferencia:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(efectivo_frame, textvariable=self.diferencia_var, font=("Arial", 13, "bold")).grid(
            row=0, column=3, padx=6, pady=6, sticky="w"
        )

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=6)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(actions, text="Guardar corte", command=self._guardar_corte).pack(side="left", padx=6)

    def _parse_fecha(self) -> date | None:
        txt = self.fecha_var.get().strip()
        try:
            return date.fromisoformat(txt)
        except Exception:
            messagebox.showwarning("Fecha inválida", "Usa el formato YYYY-MM-DD.")
            return None

    def _refresh(self):
        fecha = self._parse_fecha()
        if not fecha:
            return

        self.status_var.set("Cargando datos...")
        self.update_idletasks()

        try:
            ventas = get_ventas_por_metodo(fecha, db=self.db)
            gastos_total = get_gastos_total(fecha, db=self.db)
            propinas_total = get_propinas_total(fecha, db=self.db)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("Error", f"No se pudo cargar el resumen:\n{e}")
            return

        total_ventas = float(ventas.get("total") or 0)
        neto = total_ventas - gastos_total
        efectivo_teorico = calc_efectivo_teorico(
            ventas_efectivo=float(ventas.get("EFECTIVO") or 0),
            gastos_total=gastos_total,
            propinas_total=propinas_total,
        )

        self._last = {
            "fecha": fecha.isoformat(),
            "total_ventas": total_ventas,
            "total_gastos": gastos_total,
            "neto": neto,
            "efectivo_teorico": efectivo_teorico,
        }

        self.total_ventas_var.set(f"${total_ventas:.2f}")
        self.ventas_efectivo_var.set(f"${float(ventas.get('EFECTIVO') or 0):.2f}")
        self.ventas_tarjeta_var.set(f"${float(ventas.get('TARJETA') or 0):.2f}")
        self.ventas_transfer_var.set(f"${float(ventas.get('TRANSFER') or 0):.2f}")
        self.total_gastos_var.set(f"${gastos_total:.2f}")
        self.total_propinas_var.set(f"${propinas_total:.2f}")
        self.efectivo_teorico_var.set(f"${efectivo_teorico:.2f}")
        self.neto_var.set(f"${neto:.2f}")

        self._load_corte_existente(fecha)
        self._update_diferencia()

    def _load_corte_existente(self, fecha: date):
        try:
            corte = get_corte_por_fecha(fecha, db=self.db)
        except Exception:
            corte = None

        if corte:
            self.status_var.set(f"Corte existente para {fecha.isoformat()}.")
            self.efectivo_contado_var.set(f"{float(corte.get('efectivo_reportado') or 0):.2f}")
        else:
            self.status_var.set("No hay corte registrado para este día.")

    def _update_diferencia(self):
        try:
            efectivo_contado = float(self.efectivo_contado_var.get().strip() or 0)
        except Exception:
            self.diferencia_var.set("0.00")
            return

        efectivo_teorico = float(self._last.get("efectivo_teorico") or 0)
        diff = calc_diferencia(efectivo_contado, efectivo_teorico)
        self.diferencia_var.set(f"{diff:.2f}")

    def _guardar_corte(self):
        if not self._last:
            self._refresh()
            if not self._last:
                return

        try:
            efectivo_contado = float(self.efectivo_contado_var.get().strip())
            if efectivo_contado < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Efectivo inválido", "El efectivo contado debe ser un número >= 0.")
            return

        diferencia = calc_diferencia(efectivo_contado, float(self._last.get("efectivo_teorico") or 0))
        payload = {
            "fecha": self._last.get("fecha"),
            "total_ventas": self._last.get("total_ventas"),
            "total_gastos": self._last.get("total_gastos"),
            "neto": self._last.get("neto"),
            "efectivo_reportado": efectivo_contado,
            "diferencia_efectivo": diferencia,
            "notas": None,
        }

        try:
            save_corte(payload, db=self.db)
            messagebox.showinfo("OK", "Corte guardado.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el corte:\n{e}")
