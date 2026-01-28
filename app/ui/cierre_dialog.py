from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from services.reportes import resumen_ventas_por_metodo


class CierreDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Cierre de caja")
        self.geometry("760x520")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase

        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        self.efectivo_reportado_var = tk.StringVar()
        self.diferencia_var = tk.StringVar(value="0.00")
        self.status_var = tk.StringVar(value="")

        self.total_ventas_var = tk.StringVar(value="0.00")
        self.ventas_efectivo_var = tk.StringVar(value="0.00")
        self.ventas_tarjeta_var = tk.StringVar(value="0.00")
        self.ventas_transfer_var = tk.StringVar(value="0.00")
        self.total_gastos_var = tk.StringVar(value="0.00")
        self.neto_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._load_resumen()
        self._check_cierre()

    def _build_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(header, text="Cierre de caja", font=("Arial", 16, "bold")).pack(side="left", padx=6)

        date_row = ctk.CTkFrame(header, fg_color="transparent")
        date_row.pack(side="right")
        ctk.CTkLabel(date_row, text="Fecha (YYYY-MM-DD):").pack(side="left", padx=6)
        ctk.CTkEntry(date_row, textvariable=self.fecha_var, width=140).pack(side="left", padx=6)
        ctk.CTkButton(date_row, text="Actualizar", command=self._refresh).pack(side="left", padx=6)

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
        _row("Neto:", self.neto_var, 5)

        resumen.grid_columnconfigure(1, weight=1)

        efectivo_frame = ctk.CTkFrame(self)
        efectivo_frame.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkLabel(efectivo_frame, text="Efectivo reportado:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.efectivo_entry = ctk.CTkEntry(efectivo_frame, textvariable=self.efectivo_reportado_var, width=140)
        self.efectivo_entry.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.efectivo_entry.bind("<KeyRelease>", lambda _e: self._update_diferencia())

        ctk.CTkLabel(efectivo_frame, text="Diferencia efectivo:").grid(
            row=0, column=2, padx=6, pady=6, sticky="w"
        )
        ctk.CTkLabel(efectivo_frame, textvariable=self.diferencia_var, font=("Arial", 13, "bold")).grid(
            row=0, column=3, padx=6, pady=6, sticky="w"
        )

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=6)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        self.registrar_btn = ctk.CTkButton(actions, text="Registrar cierre", command=self._registrar_cierre)
        self.registrar_btn.pack(side="left", padx=6)

    def _parse_fecha(self) -> date | None:
        txt = self.fecha_var.get().strip()
        try:
            return date.fromisoformat(txt)
        except Exception:
            messagebox.showwarning("Fecha invalida", "Usa el formato YYYY-MM-DD.")
            return None

    def _load_resumen(self):
        fecha = self._parse_fecha()
        if not fecha:
            return

        resumen = resumen_ventas_por_metodo(fecha, db=self.db)
        total_gastos = 0.0
        try:
            gastos = self.db.listar_gastos_dia(fecha)
            total_gastos = sum(float(g.get("monto") or 0) for g in gastos)
        except Exception:
            total_gastos = 0.0

        total_ventas = float(resumen.get("total") or 0)
        neto = total_ventas - total_gastos

        self.total_ventas_var.set(f"${total_ventas:.2f}")
        self.ventas_efectivo_var.set(f"${float(resumen.get('EFECTIVO') or 0):.2f}")
        self.ventas_tarjeta_var.set(f"${float(resumen.get('TARJETA') or 0):.2f}")
        self.ventas_transfer_var.set(f"${float(resumen.get('TRANSFER') or 0):.2f}")
        self.total_gastos_var.set(f"${total_gastos:.2f}")
        self.neto_var.set(f"${neto:.2f}")

        self._update_diferencia()

    def _update_diferencia(self):
        try:
            efectivo_reportado = float(self.efectivo_reportado_var.get().strip() or 0)
        except Exception:
            self.diferencia_var.set("0.00")
            return

        try:
            ventas_efectivo = float(self.ventas_efectivo_var.get().replace("$", "").strip() or 0)
        except Exception:
            ventas_efectivo = 0.0

        diff = efectivo_reportado - ventas_efectivo
        self.diferencia_var.set(f"{diff:.2f}")

    def _check_cierre(self):
        fecha = self._parse_fecha()
        if not fecha:
            return

        cierre = None
        try:
            cierre = self.db.obtener_cierre(fecha)
        except Exception:
            cierre = None

        if cierre:
            self.status_var.set(f"Cierre ya registrado para {fecha.isoformat()}.")
            self.registrar_btn.configure(state="disabled")
            self.efectivo_entry.configure(state="disabled")
            self.efectivo_reportado_var.set(f"{float(cierre.get('efectivo_reportado') or 0):.2f}")
            self.diferencia_var.set(f"{float(cierre.get('diferencia_efectivo') or 0):.2f}")
            # Reemplaza valores de resumen por los del cierre
            self.total_ventas_var.set(f"${float(cierre.get('total_ventas') or 0):.2f}")
            self.total_gastos_var.set(f"${float(cierre.get('total_gastos') or 0):.2f}")
            self.neto_var.set(f"${float(cierre.get('neto') or 0):.2f}")
        else:
            self.status_var.set("No hay cierre registrado para este dia.")
            self.registrar_btn.configure(state="normal")
            self.efectivo_entry.configure(state="normal")

    def _refresh(self):
        self._load_resumen()
        self._check_cierre()

    def _registrar_cierre(self):
        fecha = self._parse_fecha()
        if not fecha:
            return

        try:
            efectivo_reportado = float(self.efectivo_reportado_var.get().strip())
            if efectivo_reportado < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Efectivo invalido", "El efectivo reportado debe ser un numero >= 0.")
            return

        if self.db.obtener_cierre(fecha):
            messagebox.showinfo("Cierre existente", "Ya existe un cierre para esta fecha.")
            self._check_cierre()
            return

        try:
            self.db.crear_cierre(fecha, efectivo_reportado, notas=None)
            messagebox.showinfo("OK", "Cierre registrado.")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo registrar el cierre:\n{e}")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = CierreDialog(root, db)
    dlg.mainloop()
