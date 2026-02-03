from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo

class ProductosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Catalogo de Productos")
        self.geometry("900x650")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase
        self.selected_id = None

        # Categorías estándar
        self.categorias_list = ["GENERAL", "COMIDA", "BEBIDA", "POSTRE", "EXTRAS"]
        self.menu_color = "#34495e"

        # Variables
        self.nombre_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value=self.categorias_list[0])
        self.precio_var = tk.StringVar()
        self.activo_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_productos()

    def _build_ui(self):
        # 1. HEADER
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(15, 10), pady=10)
        
        ctk.CTkLabel(header, text="CATALOGO DE PRODUCTOS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", pady=10)

        # 2. FORMULARIO EDICION
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=20)

        # -- Fila 1 Labels --
        ctk.CTkLabel(form_frame, text="Nombre del Producto", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Categoria", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Precio ($)", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, sticky="w")

        # -- Fila 2 Inputs --
        ctk.CTkEntry(form_frame, textvariable=self.nombre_var, placeholder_text="Ej: Tacos de Suadero", width=300, height=35).grid(row=1, column=0, padx=10, pady=(5, 15))
        
        # Menu con color uniforme
        ctk.CTkOptionMenu(form_frame, values=self.categorias_list, variable=self.categoria_var, width=180, height=35,
                          fg_color=self.menu_color, button_color=self.menu_color, button_hover_color="#2c3e50").grid(row=1, column=1, padx=10, pady=(5, 15))

        ctk.CTkEntry(form_frame, textvariable=self.precio_var, placeholder_text="0.00", width=120, height=35).grid(row=1, column=2, padx=10, pady=(5, 15))

        # -- Fila 3 Botones y Checkbox --
        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        
        ctk.CTkCheckBox(action_frame, text="Producto Activo (Visible en venta)", variable=self.activo_var).pack(side="left")

        # Botones alineados a la derecha
        ctk.CTkButton(action_frame, text="GUARDAR", font=("Arial", 12, "bold"), 
                      fg_color="#27ae60", hover_color="#219a52", width=150, height=35,
                      command=self._guardar).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(action_frame, text="LIMPIAR / NUEVO", font=("Arial", 12, "bold"), 
                      fg_color="#7f8c8d", hover_color="#95a5a6", width=150, height=35,
                      command=self._nuevo).pack(side="right")

        # 3. TABLA
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        cols = ("nombre", "categoria", "precio", "activo")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)

        self.tree.heading("nombre", text="Producto")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("precio", text="Precio")
        self.tree.heading("activo", text="Activo")

        self.tree.column("nombre", width=300)
        self.tree.column("categoria", width=150, anchor="center")
        self.tree.column("precio", width=100, anchor="e")
        self.tree.column("activo", width=80, anchor="center")

        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroller.pack(side="right", fill="y", padx=(0,10), pady=10)

        self.tree.bind("<Double-1>", self._on_select)

    def _load_productos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            # Usar listado completo (incluye inactivos) para gestión
            prods = self.db.listar_productos() 
            for p in prods:
                activo_str = "SI" if p.get("activo") else "NO"
                self.tree.insert("", "end", iid=str(p["id"]), values=(
                    p.get("nombre"),
                    p.get("categoria"),
                    f"${float(p.get('precio') or 0):.2f}",
                    activo_str
                ))
        except Exception as e:
            print(f"Error cargando productos: {e}")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        pid = sel[0]
        values = self.tree.item(pid, "values")
        if not values: return

        self.selected_id = int(pid)
        self.nombre_var.set(values[0])
        self.categoria_var.set(values[1])
        self.precio_var.set(values[2].replace("$", ""))
        self.activo_var.set(values[3] == "SI")

    def _nuevo(self):
        self.selected_id = None
        self.nombre_var.set("")
        self.precio_var.set("")
        self.activo_var.set(True)
        # No reseteamos categoria para agilizar captura en serie

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        categoria = self.categoria_var.get().strip() or "GENERAL"
        precio_txt = self.precio_var.get().strip()
        activo = self.activo_var.get()

        if not nombre:
            messagebox.showwarning("Falta informacion", "El nombre es obligatorio.")
            return

        try:
            precio = float(precio_txt)
            if precio < 0: raise ValueError
        except:
            messagebox.showwarning("Precio invalido", "Ingresa un precio valido mayor o igual a 0.")
            return

        try:
            if self.selected_id:
                self.db.actualizar_producto(self.selected_id, nombre=nombre, categoria=categoria, precio=precio, activo=activo)
                messagebox.showinfo("Exito", "Producto actualizado.")
            else:
                self.db.crear_producto(nombre, categoria, precio, activo=activo)
                messagebox.showinfo("Exito", "Producto creado.")
            
            self._nuevo()
            self._load_productos()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
