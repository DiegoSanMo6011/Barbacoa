from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService

class GastosDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Control de Gastos")
        self.geometry("800x600")
        self.resizable(False, False)
        # bloquea ventana de atras hasta cerrar la de enfrente
        self.grab_set()

        self.db = supabase

        # --- CONFIGURACIÓN DE CATEGORÍAS ---
        self.lista_categorias = ["INSUMOS", "GAS", "NOMINA", "MANTENIMIENTO", "GENERAL", "OTRO"]

        # Variables
        self.concepto_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value=self.lista_categorias[0])
        self.monto_var = tk.StringVar()
        self.nota_var = tk.StringVar()
        self.total_var = tk.StringVar(value="$0.00")

        self._build_ui()
        self._load_gastos()

    def _build_ui(self):
        # 1. Título Superior
        ctk.CTkLabel(self, text=" REGISTRAR NUEVO GASTO", font=("Arial", 20, "bold")).pack(pady=(15, 5))

        # 2. Frame del Formulario
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=20, pady=10)

        # --- FILA 1---
        # Label y Entry para Monto
        ctk.CTkLabel(form_frame, text="Monto ($)", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=(10,0), sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.monto_var, placeholder_text="Ej: 150.50", width=120).grid(row=1, column=0, padx=10, pady=(0,10), sticky="w")

        # Label y OptionMenu para Categoría
        ctk.CTkLabel(form_frame, text="Categoría", font=("Arial", 12)).grid(row=0, column=1, padx=10, pady=(10,0), sticky="w")
        ctk.CTkOptionMenu(form_frame, values=self.lista_categorias, variable=self.categoria_var, width=150).grid(row=1, column=1, padx=10, pady=(0,10), sticky="w")

        # --- FILA 2 ---
        # Label y Entry para Concepto
        ctk.CTkLabel(form_frame, text="Concepto (¿Qué compraste?)", font=("Arial", 12)).grid(row=2, column=0, columnspan=2, padx=10, pady=(5,0), sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.concepto_var, placeholder_text="Ej: Compra de verdura", width=300).grid(row=3, column=0, columnspan=2, padx=10, pady=(0,10), sticky="w")
        
        # Label y Entry para Nota 
        ctk.CTkLabel(form_frame, text="Nota Extra (Opcional)", font=("Arial", 12)).grid(row=2, column=2, padx=10, pady=(5,0), sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.nota_var, placeholder_text="Detalles...", width=200).grid(row=3, column=2, padx=10, pady=(0,10), sticky="w")

        # Botón de Guardar 
        btn_save = ctk.CTkButton(form_frame, text="GUARDAR GASTO 💾", fg_color="#27ae60", hover_color="#2ecc71", width=180, command=self._guardar)
        btn_save.grid(row=1, column=2, rowspan=2, padx=20, pady=10)

        # 3. Sección de Resumen y Tabla
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Header de la tabla y Total
        header_table = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        header_table.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header_table, text="HISTORIAL DE HOY", font=("Arial", 14, "bold")).pack(side="left")
        
        # Panel de Total del Día
        total_frame = ctk.CTkFrame(header_table, fg_color="#c0392b") # Rojo para indicar salida de dinero
        total_frame.pack(side="right")
        ctk.CTkLabel(total_frame, text="TOTAL GASTADO:", font=("Arial", 12, "bold"), text_color="white").pack(side="left", padx=(10, 5))
        ctk.CTkLabel(total_frame, textvariable=self.total_var, font=("Arial", 14, "bold"), text_color="white").pack(side="left", padx=(0, 10))

        # Tabla (Treeview)
        cols = ("Concepto", "Categoría", "Monto", "Nota")
        self.tree = ttk.Treeview(bottom_frame, columns=cols, show="headings", height=10)
        
        self.tree.heading("Concepto", text="Concepto")
        self.tree.heading("Categoría", text="Categoría")
        self.tree.heading("Monto", text="Monto")
        self.tree.heading("Nota", text="Nota")

        self.tree.column("Concepto", width=250)
        self.tree.column("Categoría", width=120, anchor="center")
        self.tree.column("Monto", width=100, anchor="e") # Alineado a la derecha
        self.tree.column("Nota", width=200)

        scrollbar = ttk.Scrollbar(bottom_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _guardar(self):
        concepto = self.concepto_var.get().strip()
        categoria = self.categoria_var.get()
        monto_txt = self.monto_var.get().strip()
        nota = self.nota_var.get().strip()

        # Validaciones de Piloto
        if not concepto:
            messagebox.showwarning("Falta concepto", "Por favor escribe qué compraste.")
            return

        try:
            monto = float(monto_txt)
            if monto <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Monto inválido", "El monto debe ser un número mayor a 0.")
            return

        # Guardado en Base de Datos
        try:
            self.db.crear_gasto(concepto, categoria, monto, nota)
            
            # Limpieza y Feedback
            self.concepto_var.set("")
            self.monto_var.set("")
            self.nota_var.set("")
            self._load_gastos() # Recargar tabla
            
            messagebox.showinfo("Éxito", "Gasto registrado correctamente ✅")
            
        except Exception as e:
            messagebox.showerror("Error Crítico", f"No se pudo guardar el gasto en la nube:\n{e}")

    def _load_gastos(self):
        # Limpiar tabla actual
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Cargar datos de Supabase 
        try:
            gastos = self.db.listar_gastos_dia(date.today())
            total = 0.0

            for g in gastos:
                c = g.get("concepto") or ""
                cat = g.get("categoria") or ""
                m = float(g.get("monto") or 0)
                n = g.get("nota") or ""
                
                total += m
                self.tree.insert("", "end", values=(c, cat, f"${m:.2f}", n))

            self.total_var.set(f"${total:.2f}")
            
        except Exception as e:
            print(f"Error cargando gastos: {e}") # Log en consola por si acaso
