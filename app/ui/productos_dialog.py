from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo


class ProductosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Catálogo - Productos")
        self.geometry("860x560")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.selected_id = None

        self.nombre_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value="GENERAL")
        self.precio_var = tk.StringVar()
        self.activo_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_productos()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="CATÁLOGO DE PRODUCTOS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(form, text="Nombre:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.nombre_var, width=240).grid(row=0, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Categoría:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.cat_entry = ctk.CTkEntry(form, textvariable=self.categoria_var, width=160)
        self.cat_entry.grid(row=0, column=3, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(form, text="Precio:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.precio_var, width=120).grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkCheckBox(form, text="Activo", variable=self.activo_var).grid(row=1, column=2, padx=6, pady=6, sticky="w")

        ctk.CTkButton(form, text="Guardar", command=self._guardar).grid(row=1, column=3, padx=6, pady=6, sticky="e")

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree = ttk.Treeview(table_frame, columns=("nombre", "categoria", "precio", "activo"), show="headings", height=12)
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("precio", text="Precio")
        self.tree.heading("activo", text="Activo")
        self.tree.column("nombre", width=320, anchor="w")
        self.tree.column("categoria", width=160, anchor="center")
        self.tree.column("precio", width=120, anchor="e")
        self.tree.column("activo", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Nuevo", command=self._nuevo).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Refrescar", command=self._load_productos).pack(side="left", padx=6)

    def _load_productos(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            productos = self.db.listar_productos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar catálogo:\n{e}")
            return
        for p in productos:
            activo = "SI" if p.get("activo") else "NO"
            self.tree.insert(
                "",
                "end",
                iid=str(p["id"]),
                values=(p.get("nombre"), p.get("categoria"), f"${float(p.get('precio') or 0):.2f}", activo),
            )

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        values = self.tree.item(pid, "values")
        if not values:
            return
        self.selected_id = int(pid)
        self.nombre_var.set(values[0])
        self.categoria_var.set(values[1])
        self.precio_var.set(values[2].replace("$", ""))
        self.activo_var.set(values[3] == "SI")

    def _nuevo(self):
        self.selected_id = None
        self.nombre_var.set("")
        self.categoria_var.set("GENERAL")
        self.precio_var.set("")
        self.activo_var.set(True)

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        categoria = self.categoria_var.get().strip() or "GENERAL"
        precio_txt = self.precio_var.get().strip()
        activo = self.activo_var.get()

        try:
            precio = float(precio_txt)
            if precio < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Precio inválido", "El precio debe ser un número >= 0.")
            return

        try:
            if self.selected_id:
                self.db.actualizar_producto(self.selected_id, nombre=nombre, categoria=categoria, precio=precio, activo=activo)
            else:
                self.db.crear_producto(nombre, categoria, precio, activo=activo)
            self._nuevo()
            self._load_productos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar producto:\n{e}")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = ProductosDialog(root, db)
    dlg.mainloop()
