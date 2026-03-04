from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel

class GastosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Gastos - Control de Suministros")
        self.geometry("1020x720")
        self.minsize(940, 640)
        self.resizable(True, True)
        self.grab_set()  # solo se puede interactuar con la ventana de adelante

        self.db = supabase

        # --- CONFIGURACIÓN DE CATEGORÍAS ---
        self.lista_categorias = ["INSUMOS", "GAS", "NOMINA", "MANTENIMIENTO", "GENERAL", "OTRO"]
        self.metodos_pago = ["EFECTIVO", "TARJETA", "TRANSFER"]

        # Variables de Control (Variables de Estado)
        self.monto_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value=self.lista_categorias[0])
        self.metodo_pago_var = tk.StringVar(value=self.metodos_pago[0])
        self.concepto_var = tk.StringVar()
        self.nota_var = tk.StringVar()
        self.total_dia_var = tk.StringVar(value="$0.00")
        self.selected_gasto_id: str | None = None

        self._build_ui()
        self._load_gastos()

    def _build_ui(self):
        # 1. TÍTULO CON ESTILO
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="REGISTRO DE GASTOS Y SALIDAS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        # 2. FRAME DEL FORMULARIO
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=15)
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(2, weight=1)

        # --- FILA 1: Labels de guía ---
        ctk.CTkLabel(form_frame, text="Monto ($)", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Categoría", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Método de Pago", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, sticky="w")

        # --- FILA 2: Inputs principales ---
        self.entry_monto = ctk.CTkEntry(form_frame, textvariable=self.monto_var, placeholder_text="Ej: 450.00", width=140)
        self.entry_monto.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="ew")

        self.menu_cat = ctk.CTkOptionMenu(form_frame, values=self.lista_categorias, variable=self.categoria_var, width=160)
        self.menu_cat.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="ew")

        self.menu_pago = ctk.CTkOptionMenu(form_frame, values=self.metodos_pago, variable=self.metodo_pago_var, width=160, fg_color="#34495e")
        self.menu_pago.grid(row=1, column=2, padx=10, pady=(0, 15), sticky="ew")

        # --- FILA 3: Descripción y Botón ---
        ctk.CTkLabel(form_frame, text="Concepto / Descripción del Gasto", font=("Arial", 12, "bold")).grid(row=2, column=0, columnspan=3, padx=10, sticky="w")
        
        self.entry_desc = ctk.CTkEntry(
            form_frame,
            textvariable=self.concepto_var,
            placeholder_text="¿En qué se gastó el crédito? (Ej: Compra de Cilantro)",
            width=480,
        )
        self.entry_desc.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="ew")

        # Contenedor para botones de acción
        self.action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        self.action_frame.grid(row=3, column=2, padx=10, pady=(0, 15), sticky="ew")
        
        # Botón de Guardar / Actualizar
        self.btn_save = ttk.Button(
            self.action_frame,
            text="GUARDAR GASTO",
            style="Accent.TButton",
            command=self._guardar,
        )
        self.btn_save.pack(side="left", fill="x", expand=True)
        
        # Botón de Cancelar Edición (oculto por defecto)
        self.btn_cancel = ttk.Button(
            self.action_frame,
            text="CANCELAR",
            command=self._cancel_edit,
        )
        
        # Botón de Eliminar (oculto por defecto)
        self.btn_delete = ctk.CTkButton(
            self.action_frame,
            text="ELIMINAR",
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._eliminar,
            width=80
        )

        # 3. SECCIÓN DE HISTORIAL
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Encabezado de la tabla y Totalizador
        table_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        table_header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(table_header, text="RESUMEN DE GASTOS DEL DÍA", font=("Arial", 14, "bold")).pack(side="left")
        
        total_display = ctk.CTkFrame(table_header, fg_color="#dc2626", corner_radius=8)
        total_display.pack(side="right")
        ctk.CTkLabel(total_display, text="TOTAL:", font=("Arial", 13, "bold"), text_color="white").pack(side="left", padx=10)
        ctk.CTkLabel(total_display, textvariable=self.total_dia_var, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=(0, 10))

        # Configuración de la Tabla (Treeview)
        cols = ("id", "concepto", "categoria", "metodo", "monto")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        
        self.tree.heading("id", text="ID")
        self.tree.heading("concepto", text="Descripción / Concepto")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("metodo", text="Método Pago")
        self.tree.heading("monto", text="Monto")

        self.tree.column("id", width=0, stretch=False) # Columna ID oculta
        self.tree.column("concepto", width=300)
        self.tree.column("categoria", width=120, anchor="center")
        self.tree.column("metodo", width=120, anchor="center")
        self.tree.column("monto", width=100, anchor="e")
        
        self.tree.bind("<Double-1>", self._on_item_double_click)

        # Scrollbar para la tabla
        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroller.pack(side="right", fill="y", padx=(0,10), pady=10)

        bind_mousewheel(self.tree, self.tree.yview)

    def _on_item_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return
        
        values = self.tree.item(item_id, "values")
        if not values:
            return
            
        # Extract values
        gasto_id = values[0]
        concepto = values[1]
        categoria = values[2]
        metodo = values[3]
        monto_str = values[4].replace("$", "").replace(",", "")
        
        # Populate form
        self.selected_gasto_id = gasto_id
        self.concepto_var.set(concepto)
        
        if categoria in self.lista_categorias:
            self.categoria_var.set(categoria)
            self.menu_cat.set(categoria)
            
        if metodo in self.metodos_pago:
            self.metodo_pago_var.set(metodo)
            self.menu_pago.set(metodo)
            
        self.monto_var.set(monto_str)
        
        # Update UI state for editing
        self.btn_save.configure(text="ACTUALIZAR GASTO")
        self.btn_cancel.pack(side="left", padx=(5, 0))
        self.btn_delete.pack(side="left", padx=(5, 0))

    def _cancel_edit(self):
        self.selected_gasto_id = None
        self.concepto_var.set("")
        self.monto_var.set("")
        self.categoria_var.set(self.lista_categorias[0])
        self.metodo_pago_var.set(self.metodos_pago[0])
        self.menu_cat.set(self.lista_categorias[0])
        self.menu_pago.set(self.metodos_pago[0])
        
        self.btn_save.configure(text="GUARDAR GASTO")
        self.btn_cancel.pack_forget()
        self.btn_delete.pack_forget()

    def _eliminar(self):
        if not self.selected_gasto_id:
            return
            
        if not messagebox.askyesno("Confirmar Eliminación", "¿Estás seguro que deseas eliminar este gasto?"):
            return
            
        try:
            self.db.eliminar_gasto(self.selected_gasto_id)
            messagebox.showinfo("Éxito", "Gasto eliminado correctamente.")
            self._cancel_edit()
            self._load_gastos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el gasto:\n{e}")

    def _guardar(self):
        # 1. Obtención de datos
        concepto = self.concepto_var.get().strip()
        categoria = self.categoria_var.get()
        metodo = self.metodo_pago_var.get()
        monto_raw = self.monto_var.get().strip()

        # 2. Validaciones
        if not concepto:
            messagebox.showwarning("Falta Información", "Por favor, ingresa el concepto del gasto.")
            return
        
        try:
            monto = float(monto_raw)
            if monto <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error de Monto", "Ingresa un monto válido mayor a 0.")
            return

        # 3. Guardado/Actualización en Supabase 
        try:
            if self.selected_gasto_id:
                # Update flow
                self.db.actualizar_gasto(
                    gasto_id=self.selected_gasto_id,
                    concepto=concepto,
                    categoria=categoria,
                    monto=monto,
                    metodo_pago=metodo
                )
                messagebox.showinfo("Éxito", f"Gasto actualizado correctamente.")
                self._cancel_edit()
            else:
                # Insert flow
                result = self.db.crear_gasto(
                    concepto=concepto,
                    categoria=categoria,
                    monto=monto,
                    metodo_pago=metodo
                )

                # 4. Feedback
                if isinstance(result, dict) and result.get("offline"):
                    messagebox.showwarning(
                        "Sin conexión",
                        "No se pudo sincronizar con la base de datos.\n"
                        "El gasto se guardó en cola offline para sincronizarse después."
                    )
                else:
                    messagebox.showinfo("Éxito", f"Gasto por ${monto:.2f} registrado correctamente.")
                    
                self.concepto_var.set("")
                self.monto_var.set("")
            
            self._load_gastos() # Refrescar la tabla
            
        except Exception as e:
            action = "actualizar" if self.selected_gasto_id else "registrar"
            messagebox.showerror(f"Error al {action} gasto", f"No se pudo {action} el gasto:\n{e}")

    def _load_gastos(self):
        """Carga los gastos del día actual desde la base de datos."""
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            gastos = self.db.listar_gastos_dia(date.today())
            total_acumulado = 0.0

            for g in gastos:
                m = float(g.get("monto", 0))
                total_acumulado += m
                
                self.tree.insert("", "end", values=(
                    g.get("id", ""),
                    g.get("concepto", "N/A"),
                    g.get("categoria", "GENERAL"),
                    g.get("metodo_pago", "EFECTIVO"),
                    f"${m:.2f}"
                ))

            self.total_dia_var.set(f"${total_acumulado:.2f}")

        except Exception as e:
            print(f"DEBUG: Error cargando historial: {e}")
