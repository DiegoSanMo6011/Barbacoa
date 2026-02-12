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
        self.geometry("980x640")
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.selected_id: int | None = None

        self.nombre_var = tk.StringVar()
        self.categoria_var = tk.StringVar(value="GENERAL")
        self.precio_var = tk.StringVar()
        self.orden_var = tk.StringVar(value="10")
        self.activo_var = tk.BooleanVar(value=True)
        self.venta_por_gramo_var = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar()
        self.filter_categoria_var = tk.StringVar(value="TODAS")
        self.status_var = tk.StringVar(value="")
        self._rows: list[dict] = []
        self._drag_source_id: str | None = None
        self._drag_start_y = 0

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

        ctk.CTkLabel(form, text="Orden catálogo (posición):").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.orden_var, width=90).grid(row=1, column=3, padx=6, pady=6, sticky="w")

        ctk.CTkCheckBox(form, text="Activo", variable=self.activo_var).grid(row=0, column=4, padx=6, pady=6, sticky="w")
        ctk.CTkCheckBox(
            form,
            text="Vender por gramos (precio por kg)",
            variable=self.venta_por_gramo_var,
        ).grid(row=2, column=0, columnspan=3, padx=6, pady=(2, 6), sticky="w")
        ctk.CTkLabel(
            form,
            text="Ejemplo: 100g, 250g, 1/2kg, 1kg.",
            text_color="#6b7280",
        ).grid(row=2, column=3, columnspan=2, padx=6, pady=(2, 6), sticky="w")

        ttk.Button(form, text="Guardar", style="Accent.TButton", command=self._guardar).grid(row=0, column=5, padx=6, pady=6, sticky="ew")
        ttk.Button(form, text="Nuevo", command=self._nuevo).grid(row=1, column=5, padx=6, pady=6, sticky="ew")
        ttk.Button(form, text="Refrescar", command=self._load_productos).grid(row=2, column=5, padx=6, pady=6, sticky="ew")

        tools = ctk.CTkFrame(self)
        tools.pack(fill="x", padx=12, pady=(0, 8))
        tools.grid_columnconfigure(8, weight=1)

        ctk.CTkLabel(
            tools,
            text="Reordenar: arrastra y suelta filas o usa botones rápidos.",
            text_color="#334155",
            font=("Arial", 12, "bold"),
        ).grid(row=0, column=0, columnspan=9, padx=8, pady=(8, 4), sticky="w")

        ttk.Button(tools, text="⬆ Subir", command=self._move_up).grid(row=1, column=0, padx=4, pady=6, sticky="w")
        ttk.Button(tools, text="⬇ Bajar", command=self._move_down).grid(row=1, column=1, padx=4, pady=6, sticky="w")
        ttk.Button(tools, text="⤒ Al inicio", command=self._move_top).grid(row=1, column=2, padx=4, pady=6, sticky="w")
        ttk.Button(tools, text="⤓ Al final", command=self._move_bottom).grid(row=1, column=3, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(tools, text="Buscar:").grid(row=1, column=4, padx=(10, 4), pady=6, sticky="e")
        self.search_entry = ctk.CTkEntry(tools, textvariable=self.search_var, width=180)
        self.search_entry.grid(row=1, column=5, padx=4, pady=6, sticky="w")
        self.search_entry.bind("<KeyRelease>", lambda _e: self._apply_filters())

        ctk.CTkLabel(tools, text="Categoría:").grid(row=1, column=6, padx=(10, 4), pady=6, sticky="e")
        self.filter_cat_menu = ttk.Combobox(tools, textvariable=self.filter_categoria_var, values=["TODAS"], state="readonly", width=16)
        self.filter_cat_menu.grid(row=1, column=7, padx=4, pady=6, sticky="w")
        self.filter_cat_menu.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())
        ttk.Button(tools, text="Limpiar filtro", command=self._clear_filters).grid(row=1, column=8, padx=4, pady=6, sticky="e")

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("orden", "nombre", "categoria", "precio", "activo", "gramos"),
            show="headings",
            height=14,
        )
        self.tree.heading("orden", text="Orden")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("precio", text="Precio")
        self.tree.heading("activo", text="Activo")
        self.tree.heading("gramos", text="Por gramos")
        self.tree.column("orden", width=80, anchor="center")
        self.tree.column("nombre", width=340, anchor="w")
        self.tree.column("categoria", width=190, anchor="center")
        self.tree.column("precio", width=120, anchor="e")
        self.tree.column("activo", width=90, anchor="center")
        self.tree.column("gramos", width=110, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f8fafc")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<ButtonPress-1>", self._on_tree_press, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_tree_release, add="+")

        self.bind("<Control-Up>", self._shortcut_move_up)
        self.bind("<Control-Down>", self._shortcut_move_down)
        self.bind("<Control-Shift-Up>", self._shortcut_move_top)
        self.bind("<Control-Shift-Down>", self._shortcut_move_bottom)
        self.bind("<Control-f>", self._shortcut_focus_search)
        self.bind("<Escape>", self._shortcut_clear_filters)

        status = ctk.CTkFrame(self, fg_color="transparent")
        status.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(status, textvariable=self.status_var, text_color="#475569").pack(side="left", padx=6)
        ctk.CTkLabel(
            status,
            text="Tip: arrastra para reordenar. Atajos: Ctrl+↑/↓, Ctrl+Shift+↑/↓, Ctrl+F, Esc.",
            text_color="#64748b",
        ).pack(side="right", padx=6)

    def _load_productos(self):
        try:
            productos = self.db.listar_productos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar catálogo:\n{e}")
            return
        self._rows = sorted(
            list(productos),
            key=lambda p: (
                int(p.get("orden_catalogo") or 1000),
                str(p.get("categoria") or "GENERAL"),
                str(p.get("nombre") or ""),
            ),
        )
        categorias = sorted({str(p.get("categoria") or "GENERAL") for p in self._rows})
        values = ["TODAS"] + categorias
        self.filter_cat_menu.configure(values=values)
        if self.filter_categoria_var.get() not in values:
            self.filter_categoria_var.set("TODAS")
        self._render_tree()
        if self.selected_id is None:
            self.orden_var.set(str(self._next_order_value()))
        if self.selected_id is not None:
            sid = str(self.selected_id)
            if sid in self.tree.get_children():
                self.tree.selection_set(sid)
                self.tree.focus(sid)

    def _render_tree(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        order_positions = {
            int(row.get("id")): idx + 1
            for idx, row in enumerate(self._rows)
        }
        for idx, p in enumerate(self._filtered_rows()):
            activo = "SI" if p.get("activo") else "NO"
            por_gramo = "SI" if p.get("venta_por_gramo") else "NO"
            orden = order_positions.get(int(p.get("id")), idx + 1)
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "",
                "end",
                iid=str(p["id"]),
                values=(
                    orden,
                    p.get("nombre"),
                    p.get("categoria"),
                    f"${float(p.get('precio') or 0):.2f}",
                    activo,
                    por_gramo,
                ),
                tags=(tag,),
            )
        visible = len(self.tree.get_children())
        total = len(self._rows)
        self.status_var.set(f"{visible} visibles de {total} productos.")

    def _filtered_rows(self) -> list[dict]:
        q = (self.search_var.get() or "").strip().lower()
        cat = (self.filter_categoria_var.get() or "TODAS").strip()
        rows: list[dict] = []
        for p in self._rows:
            nombre = str(p.get("nombre") or "")
            categoria = str(p.get("categoria") or "GENERAL")
            if cat != "TODAS" and categoria != cat:
                continue
            if q and q not in nombre.lower() and q not in categoria.lower():
                continue
            rows.append(p)
        return rows

    def _apply_filters(self):
        self._render_tree()

    def _clear_filters(self):
        self.search_var.set("")
        self.filter_categoria_var.set("TODAS")
        self._render_tree()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        values = self.tree.item(pid, "values")
        if not values:
            return
        self.selected_id = int(pid)
        self.orden_var.set(str(values[0]))
        self.nombre_var.set(values[1])
        self.categoria_var.set(values[2])
        self.precio_var.set(values[3].replace("$", ""))
        self.activo_var.set(values[4] == "SI")
        self.venta_por_gramo_var.set(values[5] == "SI")

    def _nuevo(self):
        self.selected_id = None
        self.nombre_var.set("")
        self.categoria_var.set("GENERAL")
        self.precio_var.set("")
        self.orden_var.set(str(self._next_order_value()))
        self.activo_var.set(True)
        self.venta_por_gramo_var.set(False)
        self.status_var.set(f"Formulario limpio. Orden sugerido: {self.orden_var.get()}.")

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        categoria = self.categoria_var.get().strip() or "GENERAL"
        precio_txt = self.precio_var.get().strip()
        orden_txt = self.orden_var.get().strip() or "1"
        activo = self.activo_var.get()
        venta_por_gramo = self.venta_por_gramo_var.get()

        try:
            precio = float(precio_txt)
            if precio < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Precio inválido", "El precio debe ser un número >= 0.")
            return
        try:
            orden_pos = int(orden_txt)
            if orden_pos <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Orden inválido", "El orden debe ser un entero >= 1.")
            return
        orden_catalogo = orden_pos * 10

        try:
            if self.selected_id:
                self.db.actualizar_producto(
                    self.selected_id,
                    nombre=nombre,
                    categoria=categoria,
                    precio=precio,
                    activo=activo,
                    venta_por_gramo=venta_por_gramo,
                    orden_catalogo=orden_catalogo,
                )
            else:
                self.db.crear_producto(
                    nombre,
                    categoria,
                    precio,
                    activo=activo,
                    venta_por_gramo=venta_por_gramo,
                    orden_catalogo=orden_catalogo,
                )
            self._nuevo()
            self._load_productos()
            self.status_var.set("Producto guardado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar producto:\n{self._format_producto_error(e)}")

    @staticmethod
    def _format_producto_error(error: Exception) -> str:
        msg = str(error)
        lower = msg.lower()
        if "orden_catalogo" in lower or "venta_por_gramo" in lower:
            return (
                f"{msg}\n\n"
                "Falta migración de productos.\n"
                "Ejecuta en Supabase: sql/productos_venta_por_gramo.sql"
            )
        return msg

    def _next_order_value(self) -> int:
        return len(self._rows) + 1

    def _selected_row_index(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        sid = int(sel[0])
        for idx, row in enumerate(self._rows):
            if int(row.get("id")) == sid:
                return idx
        return None

    def _has_active_filters(self) -> bool:
        if (self.search_var.get() or "").strip():
            return True
        return (self.filter_categoria_var.get() or "TODAS").strip() != "TODAS"

    def _ensure_reorder_context(self) -> bool:
        if not self._has_active_filters():
            return True
        messagebox.showinfo(
            "Filtro activo",
            "Para reordenar el catálogo primero limpia búsqueda/categoría (Esc).",
        )
        return False

    def _move_up(self):
        self._move_selected(-1)

    def _move_down(self):
        self._move_selected(1)

    def _move_top(self):
        self._move_to_edge(top=True)

    def _move_bottom(self):
        self._move_to_edge(top=False)

    def _move_selected(self, delta: int):
        if not self._ensure_reorder_context():
            return
        idx = self._selected_row_index()
        if idx is None:
            messagebox.showwarning("Selecciona producto", "Selecciona un producto para mover.")
            return
        target_idx = idx + delta
        if target_idx < 0 or target_idx >= len(self._rows):
            return

        current = self._rows[idx]
        current_id = int(current.get("id"))
        rows = list(self._rows)
        rows[idx], rows[target_idx] = rows[target_idx], rows[idx]
        self._persist_order(rows, current_id)

    def _move_to_edge(self, *, top: bool):
        if not self._ensure_reorder_context():
            return
        idx = self._selected_row_index()
        if idx is None:
            messagebox.showwarning("Selecciona producto", "Selecciona un producto para mover.")
            return
        current = self._rows[idx]
        current_id = int(current.get("id"))
        rows = list(self._rows)
        row = rows.pop(idx)
        if top:
            rows.insert(0, row)
        else:
            rows.append(row)
        self._persist_order(rows, current_id)

    def _persist_order(self, rows: list[dict], selected_id: int):
        try:
            for pos, row in enumerate(rows):
                rid = int(row.get("id"))
                new_order = (pos + 1) * 10
                old_order = int(row.get("orden_catalogo") or 1000)
                if old_order == new_order:
                    continue
                self.db.actualizar_producto(rid, orden_catalogo=new_order)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mover el producto:\n{self._format_producto_error(e)}")
            return

        self.selected_id = selected_id
        self._load_productos()
        sid = str(selected_id)
        if sid in self.tree.get_children():
            self.tree.selection_set(sid)
            self.tree.focus(sid)
        self.status_var.set("Orden de catálogo actualizado.")

    def _shortcut_move_up(self, _event=None):
        self._move_up()
        return "break"

    def _shortcut_move_down(self, _event=None):
        self._move_down()
        return "break"

    def _shortcut_move_top(self, _event=None):
        self._move_top()
        return "break"

    def _shortcut_move_bottom(self, _event=None):
        self._move_bottom()
        return "break"

    def _shortcut_focus_search(self, _event=None):
        self.search_entry.focus_set()
        return "break"

    def _shortcut_clear_filters(self, _event=None):
        self._clear_filters()
        return "break"

    def _on_tree_press(self, event):
        row_id = self.tree.identify_row(event.y)
        self._drag_source_id = row_id or None
        self._drag_start_y = int(event.y)

    def _on_tree_release(self, event):
        if not self._drag_source_id:
            return
        source = self._drag_source_id
        self._drag_source_id = None
        if not self._ensure_reorder_context():
            return
        if abs(int(event.y) - self._drag_start_y) < 6:
            return
        target = self.tree.identify_row(event.y)
        if not target or target == source:
            return
        source_id = int(source)
        target_id = int(target)
        source_idx = None
        target_idx = None
        for idx, row in enumerate(self._rows):
            rid = int(row.get("id"))
            if rid == source_id:
                source_idx = idx
            if rid == target_id:
                target_idx = idx
        if source_idx is None or target_idx is None:
            return
        rows = list(self._rows)
        moved = rows.pop(source_idx)
        if source_idx < target_idx:
            target_idx -= 1
        rows.insert(target_idx, moved)
        self._persist_order(rows, source_id)


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = ProductosDialog(root, db)
    dlg.mainloop()
