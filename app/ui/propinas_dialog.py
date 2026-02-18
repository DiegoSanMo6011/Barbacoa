from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel


def _set_adaptive_geometry(
    window: ctk.CTkToplevel,
    *,
    preferred_w: int,
    preferred_h: int,
    min_w: int,
    min_h: int,
):
    screen_w = int(window.winfo_screenwidth() or preferred_w)
    screen_h = int(window.winfo_screenheight() or preferred_h)

    avail_w = max(640, screen_w - 40)
    avail_h = max(480, screen_h - 90)

    width = min(preferred_w, avail_w)
    height = min(preferred_h, avail_h)

    width = max(width, min(min_w, avail_w))
    height = max(height, min(min_h, avail_h))

    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2, 0)

    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(min(min_w, width), min(min_h, height))


class PropinasEditorDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        supabase: SupabaseService,
        *,
        fecha: date,
        mesero_label: str,
        mesero_id: str | None = None,
        on_saved=None,
    ):
        super().__init__(master)
        self.title("Editar propinas")
        _set_adaptive_geometry(self, preferred_w=980, preferred_h=620, min_w=780, min_h=520)
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        self.db = supabase
        self.fecha = fecha
        self.mesero_label = (mesero_label or "").strip()
        self.mesero_id = str(mesero_id or "").strip() or None
        self.on_saved = on_saved

        self.selected_propina_id: str | None = None
        self.rows_by_id: dict[str, dict] = {}
        self.monto_var = tk.StringVar()
        self._inline_editor: tk.Entry | None = None
        self._inline_item_id: str | None = None

        self._build_ui()
        self._load_rows()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=56, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(
            header,
            text=f"EDITAR PROPINAS - {self.mesero_label or 'Sin nombre'}",
            font=("Arial", 16, "bold"),
            text_color="white",
        ).pack(side="left", padx=12, pady=12)

        meta = ctk.CTkFrame(self)
        meta.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(meta, text=f"Fecha: {self.fecha.isoformat()}", text_color="#334155").pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(meta, text="Selecciona un registro y cambia solo el monto.", text_color="#475569").pack(
            side="right", padx=6, pady=6
        )

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("hora", "origen", "monto", "tipo", "id"),
            show="headings",
            height=12,
            selectmode="browse",
        )
        self.tree.heading("hora", text="Hora")
        self.tree.heading("origen", text="Origen")
        self.tree.heading("monto", text="Monto")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("id", text="ID")

        self.tree.column("hora", width=90, anchor="center")
        self.tree.column("origen", width=130, anchor="center")
        self.tree.column("monto", width=120, anchor="e")
        self.tree.column("tipo", width=120, anchor="center")
        self.tree.column("id", width=360, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        bind_mousewheel(self.tree, self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=12, pady=(0, 12))
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(actions, text="Nuevo monto:").grid(row=0, column=0, padx=6, pady=8, sticky="w")
        ctk.CTkEntry(actions, textvariable=self.monto_var, width=140).grid(row=0, column=1, padx=6, pady=8, sticky="w")
        ttk.Button(actions, text="Guardar cambio", style="Accent.TButton", command=self._save_change).grid(
            row=0, column=2, padx=6, pady=8, sticky="ew"
        )
        ttk.Button(actions, text="Eliminar registro", command=self._delete_selected).grid(
            row=0, column=3, padx=6, pady=8, sticky="ew"
        )
        ttk.Button(actions, text="Refrescar", command=self._load_rows).grid(row=0, column=4, padx=6, pady=8, sticky="ew")
        ttk.Button(actions, text="Cerrar", command=self.destroy).grid(row=0, column=5, padx=6, pady=8, sticky="ew")

    def _load_rows(self, focus_propina_id: str | None = None):
        self._cancel_inline_edit()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.rows_by_id.clear()
        self.selected_propina_id = None
        self.monto_var.set("")

        try:
            rows = self.db.listar_propinas_dia_detalle(self.fecha)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo cargar el detalle de propinas:\n{exc}")
            return

        target_name = self.mesero_label.strip().lower()
        target_id = (self.mesero_id or "").strip().lower()
        filtered: list[dict] = []
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            row_name = str(row.get("mesero_nombre_snapshot") or "").strip()
            row_name_norm = row_name.lower() if row_name else "sin nombre"
            row_mesero_id = str(row.get("mesero_id") or "").strip().lower()
            if target_id and row_mesero_id == target_id:
                filtered.append(row)
                continue
            if row_name_norm == target_name:
                filtered.append(row)

        for row in filtered:
            propina_id = str(row.get("id") or "").strip()
            if not propina_id:
                continue
            self.rows_by_id[propina_id] = row
            fuente = str(row.get("fuente") or "NO_ESPECIFICADO").strip().upper() or "NO_ESPECIFICADO"
            monto = float(row.get("monto") or 0)
            tipo = "COMANDA" if row.get("comanda_id") else "MANUAL"
            self.tree.insert(
                "",
                "end",
                iid=propina_id,
                values=(self._hora_corta(row.get("fecha")), fuente, f"${monto:.2f}", tipo, propina_id),
            )

        if focus_propina_id and focus_propina_id in self.tree.get_children():
            self.tree.selection_set(focus_propina_id)
            self.tree.focus(focus_propina_id)
            self.tree.see(focus_propina_id)
            self._on_select()

        if not filtered:
            messagebox.showinfo("Sin registros", "No hay propinas de este mesero para la fecha seleccionada.")

    def _on_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        propina_id = str(selected[0])
        row = self.rows_by_id.get(propina_id) or {}
        self.selected_propina_id = propina_id
        self.monto_var.set(f"{float(row.get('monto') or 0):.2f}")

    def _on_tree_double_click(self, event):
        row_id = str(self.tree.identify_row(event.y) or "").strip()
        col_id = str(self.tree.identify_column(event.x) or "")
        # Solo permite edición inline en la columna Monto.
        if not row_id or col_id != "#3":
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self._start_inline_edit(row_id)
        return "break"

    def _start_inline_edit(self, propina_id: str):
        self._cancel_inline_edit()
        bbox = self.tree.bbox(propina_id, "#3")
        if not bbox:
            return
        x, y, w, h = bbox
        row = self.rows_by_id.get(propina_id) or {}
        monto_actual = float(row.get("monto") or 0)

        editor = tk.Entry(self.tree, justify="right")
        editor.insert(0, f"{monto_actual:.2f}")
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        editor.bind("<Return>", lambda _e: self._commit_inline_edit())
        editor.bind("<Escape>", lambda _e: self._cancel_inline_edit())
        editor.bind("<FocusOut>", lambda _e: self._commit_inline_edit())

        self._inline_editor = editor
        self._inline_item_id = propina_id

    def _cancel_inline_edit(self):
        if self._inline_editor is None:
            return
        try:
            self._inline_editor.destroy()
        except Exception:
            pass
        self._inline_editor = None
        self._inline_item_id = None

    def _commit_inline_edit(self):
        if self._inline_editor is None or not self._inline_item_id:
            return

        editor = self._inline_editor
        propina_id = str(self._inline_item_id)
        raw_value = (editor.get() or "").strip()
        self._inline_editor = None
        self._inline_item_id = None
        try:
            editor.destroy()
        except Exception:
            pass

        try:
            monto = float(raw_value)
            if monto <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Monto inválido", "El monto debe ser un número mayor a 0.")
            return

        self._save_amount_for_row(propina_id, monto, notify=False)

    def _save_amount_for_row(self, propina_id: str, monto: float, *, notify: bool) -> bool:
        row = self.rows_by_id.get(propina_id) or {}
        fuente = str(row.get("fuente") or "NO_ESPECIFICADO").strip().upper() or "NO_ESPECIFICADO"
        try:
            self.db.actualizar_propina(
                propina_id,
                monto=monto,
                mesero_id=row.get("mesero_id"),
                mesero_nombre_snapshot=row.get("mesero_nombre_snapshot"),
                fuente=fuente,
            )
            self._load_rows(focus_propina_id=propina_id)
            if callable(self.on_saved):
                self.on_saved()
            if notify:
                messagebox.showinfo("OK", "Propina actualizada.")
            return True
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo actualizar la propina:\n{exc}")
            return False

    def _save_change(self):
        propina_id = str(self.selected_propina_id or "").strip()
        if not propina_id:
            messagebox.showwarning("Sin selección", "Selecciona un registro para editar.")
            return
        try:
            monto = float((self.monto_var.get() or "").strip())
            if monto <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Monto inválido", "El monto debe ser un número mayor a 0.")
            return

        self._save_amount_for_row(propina_id, monto, notify=True)

    def _delete_selected(self):
        self._cancel_inline_edit()
        propina_id = str(self.selected_propina_id or "").strip()
        if not propina_id:
            messagebox.showwarning("Sin selección", "Selecciona un registro para eliminar.")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este registro de propina?"):
            return
        try:
            self.db.eliminar_propina(propina_id)
            self._load_rows()
            if callable(self.on_saved):
                self.on_saved()
            messagebox.showinfo("OK", "Propina eliminada.")
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo eliminar la propina:\n{exc}")

    @staticmethod
    def _hora_corta(fecha_raw: object) -> str:
        raw = str(fecha_raw or "").strip()
        if "T" not in raw:
            return "-"
        hhmmss = raw.split("T", 1)[1]
        hhmmss = hhmmss.replace("Z", "")
        hhmmss = hhmmss.split("+", 1)[0].split("-", 1)[0]
        return hhmmss[:8] if hhmmss else "-"


class PropinasDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Propinas")
        _set_adaptive_geometry(self, preferred_w=1080, preferred_h=760, min_w=860, min_h=620)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.mesero_map: dict[str, str] = {}
        self.detalle_rows: dict[str, dict] = {}
        self.editing_propina_id: str | None = None

        self.monto_var = tk.StringVar()
        self.mesero_var = tk.StringVar()
        self.fuente_var = tk.StringVar(value="TARJETA")
        self.mode_var = tk.StringVar(value="Modo: Registro nuevo")
        self.show_detalle_var = tk.BooleanVar(value=False)

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
        sec_a.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(sec_a, text="Registrar / editar propina", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=6, padx=6, pady=(6, 8), sticky="w"
        )
        ctk.CTkLabel(sec_a, textvariable=self.mode_var, text_color="#4b5563").grid(
            row=1, column=0, columnspan=6, padx=6, pady=(0, 8), sticky="w"
        )

        ctk.CTkLabel(sec_a, text="Monto:").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(sec_a, textvariable=self.monto_var, width=120).grid(row=2, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(sec_a, text="Mesero:").grid(row=2, column=2, padx=6, pady=6, sticky="w")
        self.mesero_menu = ctk.CTkOptionMenu(
            sec_a,
            values=[],
            variable=self.mesero_var,
            command=self._on_mesero_selected,
            width=220,
        )
        self.mesero_menu.grid(row=2, column=3, padx=6, pady=6, sticky="ew")

        ctk.CTkLabel(sec_a, text="Origen:").grid(row=3, column=0, padx=6, pady=6, sticky="w")
        self.origen_menu = ctk.CTkOptionMenu(
            sec_a,
            values=["TARJETA", "EFECTIVO", "TRANSFER", "NO_ESPECIFICADO"],
            variable=self.fuente_var,
            width=160,
        )
        self.origen_menu.grid(row=3, column=1, padx=6, pady=6, sticky="ew")

        buttons = ctk.CTkFrame(sec_a, fg_color="transparent")
        buttons.grid(row=3, column=2, columnspan=2, padx=6, pady=6, sticky="e")
        ttk.Button(buttons, text="Guardar nueva", style="Accent.TButton", command=self._guardar_propina).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Modificar propinas", command=self._abrir_editor_propinas).pack(side="left", padx=4)
        ttk.Button(buttons, text="Limpiar", command=self._reset_form).pack(side="left", padx=4)

        ctk.CTkLabel(
            sec_a,
            text="Tip: las modificaciones de propinas se hacen desde el botón 'Modificar propinas'.",
            text_color="#6b7280",
        ).grid(
            row=4,
            column=0,
            columnspan=6,
            padx=6,
            pady=(2, 6),
            sticky="w",
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

        sec_b.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(sec_b, text="Resumen por mesero (acumulado)", font=("Arial", 13, "bold")).grid(
            row=2, column=0, columnspan=5, padx=6, pady=(8, 2), sticky="w"
        )

        resumen_frame = ctk.CTkFrame(sec_b)
        resumen_frame.grid(row=3, column=0, columnspan=5, padx=6, pady=(2, 8), sticky="nsew")
        sec_b.grid_rowconfigure(3, weight=1, minsize=260)
        resumen_frame.grid_rowconfigure(0, weight=1)
        resumen_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            resumen_frame,
            columns=("sel", "mesero", "tarjeta_total", "efectivo_total", "transfer_total", "total", "num"),
            show="headings",
            height=10,
        )
        self.tree.heading("sel", text="Sel")
        self.tree.heading("mesero", text="Mesero")
        self.tree.heading("tarjeta_total", text="Tarjeta")
        self.tree.heading("efectivo_total", text="Efectivo")
        self.tree.heading("transfer_total", text="Transfer")
        self.tree.heading("total", text="Total")
        self.tree.heading("num", text="#Registros")

        self.tree.column("sel", width=64, minwidth=58, anchor="center", stretch=False)
        self.tree.column("mesero", width=260, anchor="w")
        self.tree.column("tarjeta_total", width=130, anchor="e")
        self.tree.column("efectivo_total", width=130, anchor="e")
        self.tree.column("transfer_total", width=130, anchor="e")
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("num", width=110, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(resumen_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        bind_mousewheel(self.tree, self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self._on_resumen_selected)

        self.detalle_frame = ctk.CTkFrame(sec_b)
        self.detalle_frame.grid(row=4, column=0, columnspan=5, padx=6, pady=(2, 8), sticky="nsew")
        self.detalle_frame.grid_rowconfigure(0, weight=1)
        self.detalle_frame.grid_columnconfigure(0, weight=1)

        self.detalle_tree = ttk.Treeview(
            self.detalle_frame,
            columns=("sel", "hora", "mesero", "fuente", "monto", "tipo", "id"),
            show="headings",
            height=8,
            selectmode="browse",
        )
        self.detalle_tree.heading("sel", text="Sel")
        self.detalle_tree.heading("hora", text="Hora")
        self.detalle_tree.heading("mesero", text="Mesero")
        self.detalle_tree.heading("fuente", text="Origen")
        self.detalle_tree.heading("monto", text="Monto")
        self.detalle_tree.heading("tipo", text="Tipo")
        self.detalle_tree.heading("id", text="ID")

        self.detalle_tree.column("sel", width=64, minwidth=58, anchor="center", stretch=False)
        self.detalle_tree.column("hora", width=90, anchor="center")
        self.detalle_tree.column("mesero", width=260, anchor="w")
        self.detalle_tree.column("fuente", width=120, anchor="center")
        self.detalle_tree.column("monto", width=110, anchor="e")
        self.detalle_tree.column("tipo", width=120, anchor="center")
        self.detalle_tree.column("id", width=280, anchor="w")

        self.detalle_tree.grid(row=0, column=0, sticky="nsew")
        detalle_scroll = ttk.Scrollbar(self.detalle_frame, orient="vertical", command=self.detalle_tree.yview)
        detalle_scroll.grid(row=0, column=1, sticky="ns")
        self.detalle_tree.configure(yscrollcommand=detalle_scroll.set)
        bind_mousewheel(self.detalle_tree, self.detalle_tree.yview)
        self.detalle_tree.bind("<Button-1>", self._on_detalle_click)
        self.detalle_tree.bind("<<TreeviewSelect>>", self._on_detalle_selected)
        self.detalle_frame.grid_remove()

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
        parsed = self._read_form_inputs()
        if not parsed:
            return
        monto, mesero_id, mesero_name, fuente = parsed

        try:
            self.db.crear_propina(
                monto=monto,
                mesero_id=mesero_id,
                mesero_nombre_snapshot=mesero_name,
                fuente=fuente,
                comanda_id=None,
            )
            self._reset_form()
            self._load_reporte()
            messagebox.showinfo("OK", "Propina guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la propina:\n{e}")

    def _abrir_editor_propinas(self):
        try:
            fecha = date.fromisoformat(self.fecha_var.get().strip())
        except Exception:
            messagebox.showwarning("Fecha inválida", "Usa el formato YYYY-MM-DD.")
            return

        mesero_label, mesero_id = self._selected_mesero_for_editor()
        if not mesero_label:
            messagebox.showwarning(
                "Sin selección",
                "Selecciona un mesero en el resumen (columna Sel) o en el selector de mesero.",
            )
            return

        dlg = PropinasEditorDialog(
            self,
            self.db,
            fecha=fecha,
            mesero_label=mesero_label,
            mesero_id=mesero_id,
            on_saved=self._load_reporte,
        )
        self.wait_window(dlg)

    def _selected_mesero_for_editor(self) -> tuple[str | None, str | None]:
        selected_summary = self.tree.selection()
        if selected_summary:
            values = self.tree.item(selected_summary[0], "values")
            if values and len(values) > 1:
                label = str(values[1] or "").strip()
                if label:
                    mesero_id = self.mesero_map.get(label)
                    if not mesero_id and label.strip().lower() != "sin nombre":
                        mesero_id = label
                    return label, mesero_id

        mesero_name = (self.mesero_var.get() or "").strip()
        if mesero_name:
            return mesero_name, self.mesero_map.get(mesero_name)
        return None, None

    def _actualizar_propina(self):
        propina_id = self._selected_propina_id()
        if not propina_id:
            messagebox.showwarning(
                "Sin seleccion",
                "Selecciona un mesero en el resumen o un registro en el detalle.",
            )
            return
        self.editing_propina_id = propina_id
        parsed = self._read_form_inputs()
        if not parsed:
            return
        monto, mesero_id, mesero_name, fuente = parsed
        try:
            self.db.actualizar_propina(
                propina_id,
                monto=monto,
                mesero_id=mesero_id,
                mesero_nombre_snapshot=mesero_name,
                fuente=fuente,
            )
            self._reset_form()
            self._load_reporte()
            messagebox.showinfo("OK", "Propina actualizada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar la propina:\n{e}")

    def _eliminar_propina(self):
        propina_id = self._selected_propina_id()
        if not propina_id:
            messagebox.showwarning(
                "Sin seleccion",
                "Selecciona un mesero en el resumen o un registro en el detalle.",
            )
            return

        if not messagebox.askyesno("Confirmar", "¿Eliminar la propina seleccionada? Esta acción no se puede deshacer."):
            return
        try:
            self.db.eliminar_propina(propina_id)
            self._reset_form()
            self._load_reporte()
            messagebox.showinfo("OK", "Propina eliminada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar la propina:\n{e}")

    def _read_form_inputs(self) -> tuple[float, str | None, str, str] | None:
        monto_txt = self.monto_var.get().strip()
        try:
            monto = float(monto_txt)
            if monto <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Monto invalido", "El monto debe ser un número > 0.")
            return None

        mesero_name = (self.mesero_var.get() or "").strip()
        if not mesero_name:
            messagebox.showwarning("Falta mesero", "Selecciona un mesero.")
            return None
        mesero_id = self.mesero_map.get(mesero_name)
        fuente = (self.fuente_var.get() or "").strip().upper() or "NO_ESPECIFICADO"
        return monto, mesero_id, mesero_name, fuente

    def _reset_form(self):
        self.editing_propina_id = None
        self.mode_var.set("Modo: Registro nuevo")
        self.monto_var.set("")
        self.fuente_var.set("TARJETA")
        if self.detalle_tree.selection():
            self.detalle_tree.selection_remove(self.detalle_tree.selection())
        self._refresh_checkmarks()

    def _on_detalle_selected(self, _event=None):
        selected = self.detalle_tree.selection()
        if not selected:
            return
        self._apply_row_for_edit(str(selected[0]))

    def _toggle_detalle(self):
        if self.show_detalle_var.get():
            self.detalle_frame.grid()
            return
        self.detalle_frame.grid_remove()
        self._reset_form()

    def _on_resumen_selected(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            self._refresh_resumen_checkmarks()
            return
        self._refresh_resumen_checkmarks()
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        mesero_raw = str(values[1] or "").strip()
        if not mesero_raw:
            return
        if mesero_raw in self.mesero_map:
            self.mesero_var.set(mesero_raw)
        self.editing_propina_id = None
        self.mode_var.set("Modo: Registro nuevo")
        self._refresh_checkmarks()

    def _on_detalle_click(self, event):
        region = self.detalle_tree.identify("region", event.x, event.y)
        if region not in {"tree", "cell"}:
            return
        propina_id = self.detalle_tree.identify_row(event.y)
        if not propina_id:
            return
        if self.editing_propina_id == propina_id:
            self._reset_form()
            return "break"
        self.detalle_tree.selection_set(propina_id)
        self._apply_row_for_edit(str(propina_id))
        return "break"

    def _apply_row_for_edit(self, propina_id: str):
        row = self.detalle_rows.get(propina_id) or {}
        self.editing_propina_id = propina_id
        self.mode_var.set(f"Modo: Editando ID {propina_id}")
        self.monto_var.set(f"{float(row.get('monto') or 0):.2f}")
        fuente = (row.get("fuente") or "NO_ESPECIFICADO").strip().upper()
        if fuente not in {"TARJETA", "EFECTIVO", "TRANSFER", "NO_ESPECIFICADO"}:
            fuente = "NO_ESPECIFICADO"
        self.fuente_var.set(fuente)
        mesero = (row.get("mesero_nombre_snapshot") or "").strip()
        if mesero and mesero in self.mesero_map:
            self.mesero_var.set(mesero)
        self._refresh_checkmarks()

    def _refresh_checkmarks(self):
        selected_id = str(self.editing_propina_id or "").strip()
        for iid in self.detalle_tree.get_children():
            values = list(self.detalle_tree.item(iid, "values"))
            if not values:
                continue
            values[0] = "[x]" if iid == selected_id else "[ ]"
            self.detalle_tree.item(iid, values=values)

    def _refresh_resumen_checkmarks(self):
        selected = self.tree.selection()
        selected_id = str(selected[0]).strip() if selected else ""
        for iid in self.tree.get_children():
            values = list(self.tree.item(iid, "values"))
            if not values:
                continue
            values[0] = "[x]" if str(iid).strip() == selected_id else "[ ]"
            self.tree.item(iid, values=values)

    def _selected_propina_id(self) -> str | None:
        if self.editing_propina_id:
            return str(self.editing_propina_id).strip() or None
        selected = self.detalle_tree.selection()
        if selected:
            return str(selected[0]).strip() or None
        selected_summary = self.tree.selection()
        if selected_summary:
            values = self.tree.item(selected_summary[0], "values")
            if values and len(values) > 1:
                mesero_raw = str(values[1] or "").strip()
                propina_id = self._find_propina_id_for_mesero(mesero_raw)
                if propina_id:
                    self.editing_propina_id = propina_id
                    return propina_id
        return None

    def _find_propina_id_for_mesero(self, mesero_raw: str) -> str | None:
        target = str(mesero_raw or "").strip().lower()
        if not target:
            return None
        # Recorre en orden de tabla (ya viene con más reciente primero).
        for iid in self.detalle_tree.get_children():
            row = self.detalle_rows.get(str(iid)) or {}
            row_mesero = str(row.get("mesero_nombre_snapshot") or "Sin nombre").strip().lower() or "sin nombre"
            row_mesero_id = str(row.get("mesero_id") or "").strip().lower()
            if row_mesero == target or (row_mesero_id and row_mesero_id == target):
                return str(iid)
        return None

    @staticmethod
    def _hora_corta(fecha_raw: object) -> str:
        raw = str(fecha_raw or "").strip()
        if "T" not in raw:
            return "-"
        hhmmss = raw.split("T", 1)[1]
        hhmmss = hhmmss.replace("Z", "")
        hhmmss = hhmmss.split("+", 1)[0].split("-", 1)[0]
        return hhmmss[:8] if hhmmss else "-"

    def _load_reporte(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in self.detalle_tree.get_children():
            self.detalle_tree.delete(row)
        self.detalle_rows.clear()

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
            total_tarjeta = float(r.get("total_tarjeta") or 0)
            total_efectivo = float(r.get("total_efectivo") or 0)
            total_transfer = float(r.get("total_transfer") or 0)
            self.tree.insert(
                "",
                "end",
                values=(
                    "[ ]",
                    mesero,
                    f"${total_tarjeta:.2f}",
                    f"${total_efectivo:.2f}",
                    f"${total_transfer:.2f}",
                    f"${total:.2f}",
                    num,
                ),
            )
        self._refresh_resumen_checkmarks()

        try:
            detalle_rows = self.db.listar_propinas_dia_detalle(fecha)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el detalle de propinas:\n{e}")
            return

        for row in detalle_rows:
            propina_id = str(row.get("id") or "").strip()
            if not propina_id:
                continue
            self.detalle_rows[propina_id] = row
            mesero = (row.get("mesero_nombre_snapshot") or "Sin nombre").strip() or "Sin nombre"
            fuente = (row.get("fuente") or "NO_ESPECIFICADO").strip().upper() or "NO_ESPECIFICADO"
            monto = float(row.get("monto") or 0)
            tipo = "COMANDA" if row.get("comanda_id") else "MANUAL"
            self.detalle_tree.insert(
                "",
                "end",
                iid=propina_id,
                values=("[ ]", self._hora_corta(row.get("fecha")), mesero, fuente, f"${monto:.2f}", tipo, propina_id),
            )


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = PropinasDialog(root, db)
    dlg.mainloop()
