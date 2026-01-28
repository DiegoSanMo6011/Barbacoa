from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService


class GastosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Gastos del día")
        self.geometry("760x520")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase

        self.concepto_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value="GENERAL")
        self.monto_var = tk.StringVar()
        self.nota_var = tk.StringVar()

        self.total_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._load_gastos()

    def _build_ui(self):
        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(form, text="Concepto:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.concepto_var, width=220).grid(row=0, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Categoría:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        categorias = ["GENERAL", "INSUMOS", "GAS", "NOMINA", "MANTENIMIENTO", "OTRO"]
        ctk.CTkOptionMenu(form, values=categorias, variable=self.categoria_var).grid(row=0, column=3, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Monto:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.monto_var, width=120).grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Nota:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.nota_var, width=220).grid(row=1, column=3, padx=6, pady=6, sticky="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(btns, text="Guardar", command=self._guardar).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Refresh", command=self._load_gastos).pack(side="left", padx=6)

        # Tabla de gastos del día
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=8)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("concepto", "categoria", "monto", "nota"),
            show="headings",
            height=12,
        )
        self.tree.heading("concepto", text="Concepto")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("monto", text="Monto")
        self.tree.heading("nota", text="Nota")

        self.tree.column("concepto", width=220, anchor="w")
        self.tree.column("categoria", width=140, anchor="center")
        self.tree.column("monto", width=100, anchor="e")
        self.tree.column("nota", width=240, anchor="w")

        self.tree.pack(fill="both", expand=True)

        total_row = ctk.CTkFrame(self, fg_color="transparent")
        total_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(total_row, text="Total del día:").pack(side="right", padx=(0, 6))
        ctk.CTkLabel(total_row, textvariable=self.total_var, font=("Arial", 14, "bold")).pack(side="right")

    def _guardar(self):
        concepto = self.concepto_var.get().strip()
        categoria = self.categoria_var.get().strip() or "GENERAL"
        monto_txt = self.monto_var.get().strip()
        nota = self.nota_var.get().strip() or None

        if not concepto:
            messagebox.showwarning("Falta concepto", "Escribe el concepto del gasto.")
            return
        try:
            monto = float(monto_txt)
            if monto <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Monto inválido", "El monto debe ser un número > 0.")
            return

        try:
            self.db.crear_gasto(concepto, categoria, monto, nota)
            self.concepto_var.set("")
            self.monto_var.set("")
            self.nota_var.set("")
            self._load_gastos()
            messagebox.showinfo("OK", "Gasto guardado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el gasto:\n{e}")

    def _load_gastos(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        gastos = self.db.listar_gastos_dia(date.today())
        total = 0.0

        for g in gastos:
            concepto = g.get("concepto") or ""
            categoria = g.get("categoria") or ""
            monto = float(g.get("monto") or 0)
            nota = g.get("nota") or ""
            total += monto
            self.tree.insert("", "end", values=(concepto, categoria, f"${monto:.2f}", nota))

        self.total_var.set(f"${total:.2f}")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = GastosDialog(root, db)
    dlg.mainloop()
