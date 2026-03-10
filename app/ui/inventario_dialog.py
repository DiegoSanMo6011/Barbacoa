from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel


class InventarioDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Inventario")
        self.geometry("1100x700")
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.productos = []
        self.insumos = []
        self.alertas = []

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="GESTIÓN DE INVENTARIO", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_insumos = self.tabview.add("Insumos y Alertas")
        self.tab_movimientos = self.tabview.add("Ajuste de Stock")
        self.tab_recetas = self.tabview.add("Recetas por Producto")

        self._build_tab_insumos()
        self._build_tab_movimientos()
        self._build_tab_recetas()

    # --- TAB INSUMOS ---
    def _build_tab_insumos(self):
        form = ctk.CTkFrame(self.tab_insumos)
        form.pack(fill="x", pady=(0, 12))

        self.insumo_nombre_var = tk.StringVar()
        self.insumo_unidad_var = tk.StringVar(value="kg")
        self.insumo_minimo_var = tk.StringVar(value="0")

        ctk.CTkLabel(form, text="Nombre:").grid(row=0, column=0, padx=6, pady=6)
        ctk.CTkEntry(form, textvariable=self.insumo_nombre_var, width=180).grid(row=0, column=1, padx=6, pady=6)

        ctk.CTkLabel(form, text="Unidad:").grid(row=0, column=2, padx=6, pady=6)
        ttk.Combobox(form, textvariable=self.insumo_unidad_var, values=["kg", "g", "L", "ml", "pz"], width=8, state="readonly").grid(row=0, column=3, padx=6, pady=6)

        ctk.CTkLabel(form, text="Stock Mínimo:").grid(row=0, column=4, padx=6, pady=6)
        ctk.CTkEntry(form, textvariable=self.insumo_minimo_var, width=80).grid(row=0, column=5, padx=6, pady=6)

        ttk.Button(form, text="Nuevo Insumo", style="Accent.TButton", command=self._guardar_insumo).grid(row=0, column=6, padx=12, pady=6)

        # Table
        table_frame = ctk.CTkFrame(self.tab_insumos)
        table_frame.pack(fill="both", expand=True)
        self.tree_insumos = ttk.Treeview(table_frame, columns=("nombre", "unidad", "actual", "minimo", "estado"), show="headings", height=10)
        self.tree_insumos.heading("nombre", text="Nombre")
        self.tree_insumos.heading("unidad", text="Unidad")
        self.tree_insumos.heading("actual", text="Stock Actual")
        self.tree_insumos.heading("minimo", text="Stock mínimo")
        self.tree_insumos.heading("estado", text="Estado")
        
        self.tree_insumos.column("nombre", width=300)
        self.tree_insumos.column("actual", anchor="e")
        self.tree_insumos.column("minimo", anchor="e")
        self.tree_insumos.column("estado", anchor="center")

        self.tree_insumos.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_insumos.yview)
        scroll.pack(side="right", fill="y")
        self.tree_insumos.configure(yscrollcommand=scroll.set)
        
        self.tree_insumos.tag_configure("alerta", foreground="#dc2626", font=("Arial", 11, "bold"))

        bot_insumos = ctk.CTkFrame(self.tab_insumos)
        bot_insumos.pack(fill="x", pady=12)
        ttk.Button(bot_insumos, text="Eliminar Insumo (Supr)", command=self._eliminar_insumo).pack(side="right", padx=12)
        self.tree_insumos.bind("<Delete>", self._eliminar_insumo)
        self.tree_insumos.bind("<Button-1>", self._on_tree_click)
        self.tree_insumos.bind("<Double-1>", self._on_insumo_double_click)

    def _on_tree_click(self, event):
        if getattr(self, "_current_editor", None) and self._current_editor.winfo_exists():
            self._current_editor.destroy()
            
    # --- TAB MOVIMIENTOS ---
    def _build_tab_movimientos(self):
        form = ctk.CTkFrame(self.tab_movimientos)
        form.pack(fill="x", pady=12)

        self.mov_insumo_var = tk.StringVar()
        self.mov_cantidad_var = tk.StringVar(value="0")
        self.mov_motivo_var = tk.StringVar()

        ctk.CTkLabel(form, text="Insumo:").grid(row=0, column=0, padx=6, pady=6)
        self.mov_insumo_cb = ttk.Combobox(form, textvariable=self.mov_insumo_var, state="readonly", width=30)
        self.mov_insumo_cb.grid(row=0, column=1, padx=6, pady=6)

        ctk.CTkLabel(form, text="Cantidad (positiva=entrada, negativa=salida):").grid(row=0, column=2, padx=6, pady=6)
        ctk.CTkEntry(form, textvariable=self.mov_cantidad_var, width=100).grid(row=0, column=3, padx=6, pady=6)

        ctk.CTkLabel(form, text="Motivo/Nota:").grid(row=1, column=0, padx=6, pady=6)
        ctk.CTkEntry(form, textvariable=self.mov_motivo_var, width=300).grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=6)

        ttk.Button(form, text="Ajustar Stock", style="Accent.TButton", command=self._ajustar_stock).grid(row=1, column=4, padx=12, pady=6)

    # --- TAB RECETAS ---
    def _build_tab_recetas(self):
        top = ctk.CTkFrame(self.tab_recetas)
        top.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(top, text="Producto:").pack(side="left", padx=6, pady=6)
        self.receta_prod_var = tk.StringVar()
        self.receta_prod_cb = ttk.Combobox(top, textvariable=self.receta_prod_var, state="readonly", width=40)
        self.receta_prod_cb.pack(side="left", padx=6, pady=6)
        self.receta_prod_cb.bind("<<ComboboxSelected>>", self._on_producto_receta_selected)
        
        # Guia visual de ingredientes
        self.rec_target_ings_var = tk.StringVar(value="0")
        ctk.CTkLabel(top, text="Este producto lleva:").pack(side="left", padx=(20, 2), pady=6)
        ttk.Spinbox(top, textvariable=self.rec_target_ings_var, from_=0, to=50, width=5).pack(side="left", padx=2, pady=6)
        ctk.CTkLabel(top, text="ingrediente(s)").pack(side="left", padx=2, pady=6)

        mid = ctk.CTkFrame(self.tab_recetas)
        mid.pack(fill="x", pady=(0, 12))
        self.rec_insumo_var = tk.StringVar()
        self.rec_cantidad_var = tk.StringVar(value="0")
        self.rec_unidad_var = tk.StringVar()
        
        ctk.CTkLabel(mid, text="Insumo:").pack(side="left", padx=6, pady=6)
        self.rec_insumo_cb = ttk.Combobox(mid, textvariable=self.rec_insumo_var, state="readonly", width=30)
        self.rec_insumo_cb.pack(side="left", padx=6, pady=6)
        self.rec_insumo_cb.bind("<<ComboboxSelected>>", self._on_insumo_receta_selected)
        
        ctk.CTkLabel(mid, text="Cantidad consumida:").pack(side="left", padx=6, pady=6)
        ctk.CTkEntry(mid, textvariable=self.rec_cantidad_var, width=80).pack(side="left", padx=6, pady=6)
        
        self.rec_unidad_cb = ttk.Combobox(mid, textvariable=self.rec_unidad_var, state="readonly", width=8)
        self.rec_unidad_cb.pack(side="left", padx=6, pady=6)
        
        ttk.Button(mid, text="Añadir a receta", command=self._add_receta_item).pack(side="left", padx=12, pady=6)
        ttk.Button(mid, text="Guardar Receta del Producto", style="Accent.TButton", command=self._guardar_receta).pack(side="left", padx=12, pady=6)

        table_frame = ctk.CTkFrame(self.tab_recetas)
        table_frame.pack(fill="both", expand=True)
        self.tree_recetas = ttk.Treeview(table_frame, columns=("insumo", "cantidad", "unidad", "raw_cantidad"), show="headings", height=8)
        self.tree_recetas.heading("insumo", text="Insumo")
        self.tree_recetas.heading("cantidad", text="Cantidad consumida")
        self.tree_recetas.heading("unidad", text="Unidad")
        self.tree_recetas.heading("raw_cantidad", text="") 
        
        self.tree_recetas.column("insumo", width=300)
        self.tree_recetas.column("cantidad", width=150, anchor="e")
        self.tree_recetas.column("unidad", width=100)
        
        # Hide the raw base unit data
        self.tree_recetas.column("raw_cantidad", width=0, stretch=tk.NO)
        
        self.tree_recetas.pack(side="left", fill="both", expand=True)
        self.tree_recetas.bind("<Delete>", self._remove_receta_item)

        bot = ctk.CTkFrame(self.tab_recetas)
        bot.pack(fill="x", pady=12)
        ttk.Button(bot, text="Quitar Insumo (Supr)", command=self._remove_receta_item).pack(side="left", padx=12)

    # --- LOGIC ---
    def _load_data(self):
        try:
            self.insumos = self.db.listar_insumos()
            self.productos = self.db.listar_productos()
            self.alertas = self.db.obtener_alertas_stock()
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al cargar datos: {e}")
            return

        self._render_insumos()
        
        # Populate Comboboxes
        nombres_insumos = [f"{i.nombre} ({i.unidad})" for i in self.insumos]
        self.mov_insumo_cb.configure(values=nombres_insumos)
        self.rec_insumo_cb.configure(values=nombres_insumos)

        nombres_productos = [f"[{p.get('id')}] {p.get('nombre')}" for p in self.productos]
        self.receta_prod_cb.configure(values=nombres_productos)

    def _render_insumos(self):
        for row in self.tree_insumos.get_children():
            self.tree_insumos.delete(row)
        
        alert_ids = {a.id for a in self.alertas if a.id}

        for i in self.insumos:
            estado = "OK"
            tag = ""
            if i.id in alert_ids:
                estado = "BAJO STOCK"
                tag = "alerta"
                
            self.tree_insumos.insert("", "end", iid=str(i.id), values=(
                i.nombre,
                i.unidad,
                f"{i.stock_actual:.2f}",
                f"{i.stock_minimo:.2f}",
                estado
            ), tags=(tag,))

    def _guardar_insumo(self):
        try:
            minimo = float(self.insumo_minimo_var.get() or 0)
            self.db.crear_insumo(
                nombre=self.insumo_nombre_var.get(),
                unidad=self.insumo_unidad_var.get(),
                stock_minimo=minimo
            )
            self._load_data()
            self.insumo_nombre_var.set("")
            self.insumo_minimo_var.set("0")
            messagebox.showinfo("Éxito", "Insumo creado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _eliminar_insumo(self, _e=None):
        sel = self.tree_insumos.selection()
        if not sel:
            messagebox.showwarning("Atención", "Selecciona un insumo para eliminar.\n\nNota: Si lo eliminas, desaparecerá de las recetas y su historial de stock de borrará.")
            return
            
        if not messagebox.askyesno("Confirmar", "¿Seguro que deseas eliminar el insumo seleccionado de forma permanente?"):
            return
            
        try:
            for s in sel:
                self.db.eliminar_insumo(s)
            self._load_data()
            messagebox.showinfo("Éxito", "Insumo(s) eliminado(s).")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar: {e}")

    def _on_insumo_double_click(self, event):
        region = self.tree_insumos.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        row_id = self.tree_insumos.identify_row(event.y)
        column_id = self.tree_insumos.identify_column(event.x)
        if not row_id or not column_id: return
        
        col_idx = int(column_id.replace("#", "")) - 1
        # No edit status (col 4). Col 0=nombre, 1=unidad, 2=actual, 3=minimo
        if col_idx >= 4: return
        
        x, y, width, height = self.tree_insumos.bbox(row_id, column_id)
        current_value = self.tree_insumos.item(row_id, "values")[col_idx]
        
        if col_idx == 1: # Unidad
            editor = ttk.Combobox(self.tree_insumos, values=["kg", "g", "L", "ml", "pz"], state="readonly")
            editor.set(current_value)
        else:
            editor = tk.Entry(self.tree_insumos)
            editor.insert(0, current_value)
            editor.select_range(0, tk.END)
            
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        
        def on_save(_event=None):
            new_val = editor.get()
            editor.destroy()
            self._commit_edit(row_id, col_idx, new_val)
            
        editor.bind("<Return>", on_save)
        # Handle ttk.Combobox dropdown selection applying
        if col_idx == 1:
            editor.bind("<<ComboboxSelected>>", on_save)
        else:
            editor.bind("<FocusOut>", lambda e: editor.destroy())
            
        editor.bind("<Escape>", lambda e: editor.destroy())
        self._current_editor = editor

    def _commit_edit(self, row_id, col_idx, new_val):
        insumo = next((i for i in self.insumos if str(i.id) == row_id), None)
        if not insumo: return
        
        try:
            changes = {}
            if col_idx == 0:
                if not new_val.strip(): raise ValueError("El nombre no puede estar vacío.")
                changes["nombre"] = new_val.strip()
            elif col_idx == 1:
                if not new_val.strip(): raise ValueError("La unidad no puede estar vacía.")
                changes["unidad"] = new_val.strip()
            elif col_idx == 2:
                changes["stock_actual"] = float(new_val)
                if changes["stock_actual"] < 0: raise ValueError("Stock no puede ser negativo.")
            elif col_idx == 3:
                changes["stock_minimo"] = float(new_val)
                if changes["stock_minimo"] < 0: raise ValueError("Stock mínimo no puede ser negativo.")
                
            self.db.actualizar_insumo(row_id, changes)
            self._load_data()
        except ValueError as ve:
            messagebox.showwarning("Atención", str(ve))
            self._load_data()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")


    def _ajustar_stock(self):
        sel_idx = self.mov_insumo_cb.current()
        if sel_idx < 0:
            return messagebox.showwarning("Atención", "Selecciona un insumo.")
        insumo = self.insumos[sel_idx]
        
        try:
            cant = float(self.mov_cantidad_var.get())
            if cant == 0: return
        except Exception:
            return messagebox.showwarning("Atención", "Cantidad inválida.")
            
        try:
            self.db.ajustar_stock_insumo(
                insumo_id=str(insumo.id),
                current_stock=insumo.stock_actual,
                amount_to_add=cant,
                descripcion=self.mov_motivo_var.get() or "AJUSTE MANUAL"
            )
            self._load_data()
            self.mov_cantidad_var.set("0")
            self.mov_motivo_var.set("")
            self.tabview.set("Insumos y Alertas")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_insumo_receta_selected(self, _e=None):
        sel_idx = self.rec_insumo_cb.current()
        if sel_idx < 0: return
        insumo = self.insumos[sel_idx]
        
        # Allow all units universally to support custom mappings
        opciones_unidad = ["kg", "g", "L", "ml", "pz"]
            
        self.rec_unidad_cb.configure(values=opciones_unidad)
        self.rec_unidad_var.set(insumo.unidad) # Default to the base unit


    def _on_producto_receta_selected(self, _e=None):
        if len(self.tree_recetas.get_children()) > 0:
            if not messagebox.askyesno("Cambiar Producto", "Tienes ingredientes no guardados en esta receta. ¿Seguro que quieres cambiar de producto y perder tus cambios sin guardar?"):
                # Revert selection
                return
                
        sel_idx = self.receta_prod_cb.current()
        if sel_idx < 0: return
        prod = self.productos[sel_idx]
        pid = int(prod.get("id"))
        
        for row in self.tree_recetas.get_children():
            self.tree_recetas.delete(row)
            
        try:
            recetas = self.db.obtener_recetas_producto(pid)
            insumo_dict = {str(i.id): i for i in self.insumos}
            
            for r in recetas:
                ins = insumo_dict.get(str(r.insumo_id))
                if ins:
                    mostrar_cantidad = r.cantidad
                    mostrar_unidad = ins.unidad
                    
                    # Auto upscale for visual readability
                    if ins.unidad == "kg" and r.cantidad < 1.0 and r.cantidad > 0:
                        mostrar_cantidad = r.cantidad * 1000.0
                        mostrar_unidad = "g"
                    elif ins.unidad == "L" and r.cantidad < 1.0 and r.cantidad > 0:
                        mostrar_cantidad = r.cantidad * 1000.0
                        mostrar_unidad = "ml"
                        
                    self.tree_recetas.insert("", "end", iid=r.insumo_id, values=(
                        ins.nombre, mostrar_cantidad, mostrar_unidad, r.cantidad
                    ))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar receta: {e}")

    def _add_receta_item(self):
        sel_idx = self.rec_insumo_cb.current()
        if sel_idx < 0: return
        insumo = self.insumos[sel_idx]
        iid = str(insumo.id)
        
        try:
            mostrar_cant = float(self.rec_cantidad_var.get())
            if mostrar_cant <= 0: raise ValueError
        except:
            return messagebox.showwarning("Atención", "Cantidad inválida (debe ser > 0).")
            
        unidad_seleccionada = self.rec_unidad_var.get()
        if not unidad_seleccionada:
            return messagebox.showwarning("Atención", "Selecciona una unidad.")
            
        # Convert to Base Unit
        raw_cant = mostrar_cant
        
        # 1. Standard mathematically known conversions
        is_standard = False
        if insumo.unidad == "kg" and unidad_seleccionada == "g":
            raw_cant = mostrar_cant / 1000.0
            is_standard = True
        elif insumo.unidad == "L" and unidad_seleccionada == "ml":
            raw_cant = mostrar_cant / 1000.0
            is_standard = True
        elif insumo.unidad == "g" and unidad_seleccionada == "kg":
            raw_cant = mostrar_cant * 1000.0
            is_standard = True
        elif insumo.unidad == unidad_seleccionada:
            is_standard = True
            
        # 2. Arbitrary custom conversions (e.g. pz -> kg)
        if not is_standard:
            import tkinter.simpledialog as sd
            msg = f"Este insumo se guarda en '{insumo.unidad}', pero seleccionaste '{unidad_seleccionada}'.\n\n¿A cuánto equivale 1 {unidad_seleccionada} en {insumo.unidad}?"
            peso_unitario_str = sd.askstring("Equivalencia", msg, parent=self)
            if not peso_unitario_str: 
                return # Cancelled
            try:
                peso_unitario = float(peso_unitario_str)
                if peso_unitario <= 0: raise ValueError
            except ValueError:
                return messagebox.showwarning("Error", "Equivalencia inválida. Debe ser un número mayor a 0.")
                
            raw_cant = mostrar_cant * peso_unitario

        if self.tree_recetas.exists(iid):
            self.tree_recetas.item(iid, values=(insumo.nombre, mostrar_cant, unidad_seleccionada, raw_cant))
        else:
            self.tree_recetas.insert("", "end", iid=iid, values=(insumo.nombre, mostrar_cant, unidad_seleccionada, raw_cant))

    def _remove_receta_item(self, _e=None):
        sel = self.tree_recetas.selection()
        for s in sel:
            self.tree_recetas.delete(s)

    def _guardar_receta(self):
        sel_idx = self.receta_prod_cb.current()
        if sel_idx < 0:
            return messagebox.showwarning("Atención", "Selecciona un producto primero.")
        pid = int(self.productos[sel_idx].get("id"))
        
        recetas_data = []
        for row_id in self.tree_recetas.get_children():
            vals = self.tree_recetas.item(row_id, "values")
            # Get the exact raw database quantity stored in the hidden 4th column
            raw_cantidad = float(vals[3]) 
            recetas_data.append({
                "producto_id": pid,
                "insumo_id": row_id,
                "cantidad": raw_cantidad
            })
            
        try:
            self.db.guardar_recetas_producto(pid, recetas_data)
            messagebox.showinfo("Éxito", "Receta guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"Falla al guardar receta: {e}")

if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = InventarioDialog(root, db)
    dlg.mainloop()
