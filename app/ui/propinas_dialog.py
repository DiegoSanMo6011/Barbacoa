from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel


class PropinasDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Propinas")
        self.geometry("980x680")
        self.minsize(900, 620)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.mesero_map: dict[str, str] = {}

        self.monto_var = tk.StringVar()
        self.mesero_var = tk.StringVar()
        self.fuente_var = tk.StringVar(value="TARJETA")

        today = date.today()
        self.fecha_var = tk.StringVar(value=today.isoformat())

        self._build_ui()
        self._load_meseros()
        self._load_reporte()

    def _build_ui(self):
        # Section A: registro
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="PROPINAS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        sec_a = ctk.CTkFrame(self)
        sec_a.pack(fill="x", padx=12, pady=12)
        sec_a.grid_columnconfigure(1, weight=1)
        sec_a.grid_columnconfigure(3, weight=1)
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
            width=220,
        )
        self.mesero_menu.grid(row=1, column=3, padx=6, pady=6, sticky="ew")

        ctk.CTkLabel(sec_a, text="Origen:").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        self.origen_menu = ctk.CTkOptionMenu(
            sec_a,
            values=["TARJETA", "EFECTIVO", "TRANSFER", "NO_ESPECIFICADO"],
            variable=self.fuente_var,
            width=160,
        )
        self.origen_menu.grid(row=2, column=1, padx=6, pady=6, sticky="ew")

        ttk.Button(sec_a, text="Guardar", style="Accent.TButton", command=self._guardar_propina).grid(
            row=2, column=3, padx=6, pady=6, sticky="ew"
        )

        # Section B: reporte diario
        sec_b = ctk.CTkFrame(self)
        sec_b.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkLabel(sec_b, text="Reporte diario", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=5, padx=6, pady=(10, 6), sticky="w"
        )

        ctk.CTkLabel(sec_b, text="Fecha (YYYY-MM-DD):").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.fecha_entry = ctk.CTkEntry(sec_b, textvariable=self.fecha_var, width=160)
        self.fecha_entry.grid(row=1, column=1, padx=6, pady=6, sticky="w")
        self.fecha_entry.bind("<Return>", lambda _e: self._load_reporte())

        ttk.Button(sec_b, text="Actualizar", command=self._load_reporte).grid(
            row=1, column=4, padx=6, pady=6, sticky="e"
        )

        table_frame = ctk.CTkFrame(sec_b)
        table_frame.grid(row=2, column=0, columnspan=5, padx=6, pady=8, sticky="nsew")
        sec_b.grid_rowconfigure(2, weight=1)
        sec_b.grid_columnconfigure(4, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("mesero", "tarjeta_num", "tarjeta_total", "total", "num"),
            show="headings",
            height=12,
        )
        self.tree.heading("mesero", text="Mesero")
        self.tree.heading("tarjeta_num", text="#Tarjeta")
        self.tree.heading("tarjeta_total", text="Total Tarjeta")
        self.tree.heading("total", text="Total")
        self.tree.heading("num", text="#Registros")

        self.tree.column("mesero", width=300, anchor="w")
        self.tree.column("tarjeta_num", width=90, anchor="center")
        self.tree.column("tarjeta_total", width=140, anchor="e")
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("num", width=120, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        bind_mousewheel(self.tree, self.tree.yview)

    def _on_mesero_selected(self, value: str):
        # Usa el nombre del menu como snapshot
        return

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

        values = names
        self.mesero_menu.configure(values=values)
        if values:
            self.mesero_var.set(values[0])
            self._on_mesero_selected(values[0])

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
        mesero_id = self.mesero_map.get(sel)
        mesero_name = sel or None
        if not mesero_name:
            messagebox.showwarning("Falta mesero", "Selecciona un mesero.")
            return

        try:
            self.db.crear_propina(
                monto=monto,
                mesero_id=mesero_id,
                mesero_nombre_snapshot=mesero_name,
                fuente=self.fuente_var.get().strip(),
                comanda_id=None,
            )
            self.monto_var.set("")
            self.fuente_var.set("TARJETA")
            self._load_reporte()
            messagebox.showinfo("OK", "Propina guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la propina:\n{e}")

    def _load_reporte(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            fecha = date.fromisoformat(self.fecha_var.get().strip())
        except Exception:
            messagebox.showwarning("Fecha inválida", "Usa el formato YYYY-MM-DD.")
            return

        try:
            rows = self.db.reporte_propinas_dia(fecha)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el reporte:\n{e}")
            return

        for r in rows:
            mesero = r.get("mesero") or "Sin nombre"
            total = float(r.get("total_propinas") or 0)
            num = int(r.get("num_propinas") or 0)
            num_tarjeta = int(r.get("num_tarjeta") or 0)
            total_tarjeta = float(r.get("total_tarjeta") or 0)
            self.tree.insert(
                "",
                "end",
                values=(mesero, num_tarjeta, f"${total_tarjeta:.2f}", f"${total:.2f}", num),
            )


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = PropinasDialog(root, db)
    dlg.mainloop()
