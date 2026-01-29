from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService

class GastosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Módulo de Gastos - Control de Suministros")
        self.geometry("850x650")
        self.resizable(False, False)
        self.grab_set()  # solo se puede interactuar con la ventana de adelante

        self.db = supabase

        # --- CONFIGURACIÓN DE CATEGORÍAS ---
        self.lista_categorias = ["INSUMOS", "GAS", "NOMINA", "MANTENIMIENTO", "GENERAL", "OTRO"]
        self.metodos_pago = ["EFECTIVO", "TARJETA", "TRANSFERENCIA"]

        # Variables de Control (Variables de Estado)
        self.monto_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value=self.lista_categorias[0])
        self.metodo_pago_var = tk.StringVar(value=self.metodos_pago[0])
        self.concepto_var = tk.StringVar()
        self.nota_var = tk.StringVar()
        self.total_dia_var = tk.StringVar(value="$0.00")

        self._build_ui()
        self._load_gastos()

    def _build_ui(self):
        # 1. TÍTULO CON ESTILO
        header = ctk.CTkFrame(self, fg_color="#2c3e50", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="📦 REGISTRO DE GASTOS Y SALIDAS", font=("Arial", 22, "bold"), text_color="white").pack(pady=15)

        # 2. FRAME DEL FORMULARIO
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=15)

        # --- FILA 1: Labels de guía ---
        ctk.CTkLabel(form_frame, text="Monto ($)", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Categoría", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Método de Pago", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, sticky="w")

        # --- FILA 2: Inputs principales ---
        self.entry_monto = ctk.CTkEntry(form_frame, textvariable=self.monto_var, placeholder_text="Ej: 450.00", width=140)
        self.entry_monto.grid(row=1, column=0, padx=10, pady=(0, 15))

        self.menu_cat = ctk.CTkOptionMenu(form_frame, values=self.lista_categorias, variable=self.categoria_var, width=160)
        self.menu_cat.grid(row=1, column=1, padx=10, pady=(0, 15))

        self.menu_pago = ctk.CTkOptionMenu(form_frame, values=self.metodos_pago, variable=self.metodo_pago_var, width=160, fg_color="#34495e")
        self.menu_pago.grid(row=1, column=2, padx=10, pady=(0, 15))

        # --- FILA 3: Descripción y Botón ---
        ctk.CTkLabel(form_frame, text="Concepto / Descripción del Gasto", font=("Arial", 12, "bold")).grid(row=2, column=0, columnspan=2, padx=10, sticky="w")
        
        self.entry_desc = ctk.CTkEntry(form_frame, textvariable=self.concepto_var, placeholder_text="¿En qué se gastó el crédito? (Ej: Compra de Cilantro)", width=480)
        self.entry_desc.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 15), sticky="w")

        # Botón de Guardar 
        self.btn_save = ctk.CTkButton(form_frame, text="GUARDAR GASTO 💾", font=("Arial", 14, "bold"), 
                                     fg_color="#27ae60", hover_color="#1e8449", height=40,
                                     command=self._guardar)
        self.btn_save.grid(row=3, column=2, padx=10, pady=(0, 15), sticky="e")

        # 3. SECCIÓN DE HISTORIAL
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Encabezado de la tabla y Totalizador
        table_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        table_header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(table_header, text="RESUMEN DE GASTOS DEL DÍA", font=("Arial", 14, "bold")).pack(side="left")
        
        total_display = ctk.CTkFrame(table_header, fg_color="#e74c3c", corner_radius=8)
        total_display.pack(side="right")
        ctk.CTkLabel(total_display, text="TOTAL:", font=("Arial", 13, "bold"), text_color="white").pack(side="left", padx=10)
        ctk.CTkLabel(total_display, textvariable=self.total_dia_var, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=(0, 10))

        # Configuración de la Tabla (Treeview)
        cols = ("concepto", "categoria", "metodo", "monto")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        
        self.tree.heading("concepto", text="Descripción / Concepto")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("metodo", text="Método Pago")
        self.tree.heading("monto", text="Monto")

        self.tree.column("concepto", width=300)
        self.tree.column("categoria", width=120, anchor="center")
        self.tree.column("metodo", width=120, anchor="center")
        self.tree.column("monto", width=100, anchor="e")

        # Scrollbar para la tabla
        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroller.pack(side="right", fill="y", padx=(0,10), pady=10)

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

        # 3. Guardado en Supabase 
        try:
            #supabase_service ahora recibe metodo_pago
            self.db.crear_gasto(
                concepto=concepto,
                categoria=categoria,
                monto=monto,
                metodo_pago=metodo
            )
            
            # 4. Feedback y Limpieza
            messagebox.showinfo("Éxito", f"Gasto por ${monto:.2f} registrado correctamente. ✅")
            self.concepto_var.set("")
            self.monto_var.set("")
            self._load_gastos() # Refrescar la tabla
            
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo sincronizar con la base de datos:\n{e}")

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
                    g.get("concepto", "N/A"),
                    g.get("categoria", "GENERAL"),
                    g.get("metodo_pago", "EFECTIVO"),
                    f"${m:.2f}"
                ))

            self.total_dia_var.set(f"${total_acumulado:.2f}")

        except Exception as e:
            print(f"DEBUG: Error cargando historial: {e}")
