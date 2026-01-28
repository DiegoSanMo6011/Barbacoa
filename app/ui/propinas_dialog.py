from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService


class PropinasDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Propinas")
        self.geometry("820x560")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.mesero_map: dict[str, str] = {}

        self.monto_var = tk.StringVar()
        self.mesero_var = tk.StringVar(value="OTRO / MANUAL")
        self.mesero_manual_var = tk.StringVar()

        today = date.today()
        self.year_var = tk.StringVar(value=str(today.year))
        self.month_var = tk.StringVar(value=str(today.month))

        self._build_ui()
        self._load_meseros()
        self._load_reporte()

    def _build_ui(self):
        # Section A: registro manual
        sec_a = ctk.CTkFrame(self)
        sec_a.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(sec_a, text="Registrar propina manual", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=4, padx=6, pady=(6, 10), sticky="w"
        )

        ctk.CTkLabel(sec_a, text="Monto:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(sec_a, textvariable=self.monto_var, width=120).grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(sec_a, text="Mesero:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        self.mesero_menu = ctk.CTkOptionMenu(
            sec_a,
            values=["OTRO / MANUAL"],
            variable=self.mesero_var,
            command=self._on_mesero_selected,
        )
        self.mesero_menu.grid(row=1, column=3, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(sec_a, text="Nombre manual:").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        self.mesero_manual_entry = ctk.CTkEntry(sec_a, textvariable=self.mesero_manual_var, width=220)
        self.mesero_manual_entry.grid(row=2, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkButton(sec_a, text="Guardar", command=self._guardar_propina).grid(
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

        ctk.CTkButton(sec_b, text="Actualizar", command=self._load_reporte).grid(
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
        self.tree.heading("total", text="Total")
        self.tree.heading("num", text="#Registros")

        self.tree.column("mesero", width=260, anchor="w")
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("num", width=120, anchor="center")

        self.tree.pack(fill="both", expand=True)

    def _on_mesero_selected(self, value: str):
        if value == "OTRO / MANUAL":
            self.mesero_manual_entry.configure(state="normal")
            self.mesero_manual_var.set("")
            self.mesero_manual_entry.focus()
            return

        # Bloquea entrada manual y usa el nombre del menu como snapshot
        self.mesero_manual_entry.configure(state="disabled")
        self.mesero_manual_var.set(value)

    def _load_meseros(self):
        try:
            res = (
                self.db.client.table("meseros")
                .select("id, nombre")
                .eq("activo", True)
                .order("nombre")
                .execute()
            )
            data = res.data or []
        except Exception:
            data = []

        self.mesero_map.clear()
        names = []
        for m in data:
            nombre = (m.get("nombre") or "").strip()
            mid = m.get("id")
            if not nombre or not mid:
                continue
            self.mesero_map[nombre] = mid
            names.append(nombre)

        values = names + ["OTRO / MANUAL"]
        self.mesero_menu.configure(values=values)
        self.mesero_var.set("OTRO / MANUAL")
        self._on_mesero_selected("OTRO / MANUAL")

    def _guardar_propina(self):
        monto_txt = self.monto_var.get().strip()
        try:
            monto = float(monto_txt)
            if monto <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Monto invalido", "El monto debe ser un numero > 0.")
            return

        sel = self.mesero_var.get()
        if sel != "OTRO / MANUAL":
            mesero_id = self.mesero_map.get(sel)
            mesero_name = sel
        else:
            mesero_id = None
            mesero_name = self.mesero_manual_var.get().strip() or None
            if not mesero_name:
                messagebox.showwarning("Falta mesero", "Escribe el nombre del mesero.")
                return

        try:
            self.db.crear_propina(
                monto=monto,
                mesero_id=mesero_id,
                mesero_nombre_snapshot=mesero_name,
                fuente="MANUAL",
                comanda_id=None,
            )
            self.monto_var.set("")
            if sel == "OTRO / MANUAL":
                self.mesero_manual_var.set("")
            self._load_reporte()
            messagebox.showinfo("OK", "Propina guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la propina:\n{e}")

    def _load_reporte(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            year = int(self.year_var.get())
            month = int(self.month_var.get())
        except Exception:
            messagebox.showwarning("Fecha invalida", "Selecciona un ano y mes validos.")
            return

        try:
            rows = self.db.reporte_propinas_mes(year, month)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el reporte:\n{e}")
            return

        for r in rows:
            mesero = r.get("mesero") or "Sin nombre"
            total = float(r.get("total_propinas") or 0)
            num = int(r.get("num_propinas") or 0)
            self.tree.insert("", "end", values=(mesero, f"${total:.2f}", num))


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = PropinasDialog(root, db)
    dlg.mainloop()
