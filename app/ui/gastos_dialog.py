from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo

class GastosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Control de Gastos")
        self.geometry("850x650")
        self.resizable(False, False)
        self.grab_set()

        self.db = supabase

        # --- CONFIGURACIÓN ---
        self.lista_categorias = ["INSUMOS", "GAS", "NOMINA", "MANTENIMIENTO", "GENERAL", "OTRO"]
        self.metodos_pago = ["EFECTIVO", "TARJETA", "TRANSFERENCIA"]
        # Color para menús planos y uniformes
        self.menu_color = "#34495e"

        # Variables
        self.monto_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value=self.lista_categorias[0])
        self.metodo_pago_var = tk.StringVar(value=self.metodos_pago[0])
        self.concepto_var = tk.StringVar()
        self.total_dia_var = tk.StringVar(value="$0.00")

        self._build_ui()
        self._load_gastos()

    def _build_ui(self):
        # 1. HEADER ESTANDARIZADO CON LOGO
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(15, 10), pady=10)
        # Título sin emoji, texto claro y profesional
        ctk.CTkLabel(header, text="REGISTRO DE GASTOS Y SALIDAS", font=("Arial", 20, "bold"), text_color="white").pack(side="left", pady=10)

        # 2. FORMULARIO
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=20)

        # --- FILA 1: Monto, Categoría, Método ---
        # Labels superiores para claridad
        ctk.CTkLabel(form_frame, text="Monto ($)", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Categoría", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=10, sticky="w")
        ctk.CTkLabel(form_frame, text="Método de Pago", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, sticky="w")

        # Inputs
        self.entry_monto = ctk.CTkEntry(form_frame, textvariable=self.monto_var, placeholder_text="Ej: 450.00", width=150, height=35, font=("Arial", 14))
        self.entry_monto.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="w")

        # Menús con color uniforme (sin doble tono azul)
        self.menu_cat = ctk.CTkOptionMenu(form_frame, values=self.lista_categorias, variable=self.categoria_var, width=180, height=35,
                                          fg_color=self.menu_color, button_color=self.menu_color, button_hover_color="#2c3e50", font=("Arial", 12))
        self.menu_cat.grid(row=1, column=1, padx=10, pady=(5, 15), sticky="w")

        self.menu_pago = ctk.CTkOptionMenu(form_frame, values=self.metodos_pago, variable=self.metodo_pago_var, width=180, height=35,
                                           fg_color=self.menu_color, button_color=self.menu_color, button_hover_color="#2c3e50", font=("Arial", 12))
        self.menu_pago.grid(row=1, column=2, padx=10, pady=(5, 15), sticky="w")

        # --- FILA 2: Concepto y Botón de Guardar ---
        ctk.CTkLabel(form_frame, text="Concepto / Descripción del Gasto", font=("Arial", 12, "bold")).grid(row=2, column=0, columnspan=2, padx=10, sticky="w")
        
        # Campo de descripción más ancho
        self.entry_desc = ctk.CTkEntry(form_frame, textvariable=self.concepto_var, placeholder_text="¿En qué se gastó? (Ej: Compra de insumos)", width=540, height=35, font=("Arial", 14))
        self.entry_desc.grid(row=3, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="w")

        # Botón de Guardar 
        self.btn_save = ttk.Button(
            form_frame,
            text="GUARDAR GASTO",
            style="Accent.TButton",
            command=self._guardar,
        )
        self.btn_save.grid(row=3, column=2, padx=10, pady=(0, 15), sticky="e")

        # 3. HISTORIAL Y TOTALES
        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Header de tabla con Totalizador
        table_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        table_header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(table_header, text="GASTOS DEL DÍA", font=("Arial", 14, "bold")).pack(side="left")
        
        # Totalizador en rojo para resaltar salida de dinero
        total_display = ctk.CTkFrame(table_header, fg_color="#c0392b", corner_radius=6)
        total_display.pack(side="right")
        ctk.CTkLabel(total_display, text="TOTAL:", font=("Arial", 12, "bold"), text_color="white").pack(side="left", padx=(10, 5))
        ctk.CTkLabel(total_display, textvariable=self.total_dia_var, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=(0, 10))

        # Tabla (Treeview) - Estilo estándar
        cols = ("concepto", "categoria", "metodo", "monto")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        
        self.tree.heading("concepto", text="Concepto")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("metodo", text="Método")
        self.tree.heading("monto", text="Monto")

        self.tree.column("concepto", width=320)
        self.tree.column("categoria", width=130, anchor="center")
        self.tree.column("metodo", width=130, anchor="center")
        self.tree.column("monto", width=110, anchor="e")

        scroller = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroller.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroller.pack(side="right", fill="y", padx=(0,10), pady=10)

    def _guardar(self):
        # Lógica de guardado (sin cambios funcionales, solo se quitaron emojis de los mensajes)
        concepto = self.concepto_var.get().strip()
        categoria = self.categoria_var.get()
        metodo = self.metodo_pago_var.get()
        monto_raw = self.monto_var.get().strip()

        if not concepto:
            messagebox.showwarning("Falta Información", "Por favor, ingresa el concepto del gasto.")
            return
        
        try:
            monto = float(monto_raw)
            if monto <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error de Monto", "Ingresa un monto válido mayor a 0.")
            return

        try:
            self.db.crear_gasto(
                concepto=concepto,
                categoria=categoria,
                monto=monto,
                metodo_pago=metodo
            )
            # Mensaje de éxito limpio, sin emojis
            messagebox.showinfo("Éxito", f"Gasto de ${monto:.2f} registrado correctamente.")
            self.concepto_var.set("")
            self.monto_var.set("")
            self._load_gastos()
            self.entry_monto.focus_set() # Regresar foco al primer campo
            
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo guardar el gasto:\n{e}")

    def _load_gastos(self):
        # Lógica de carga (sin cambios)
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
            print(f"Error cargando historial de gastos: {e}")
