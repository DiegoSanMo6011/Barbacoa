from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from services.supabase_service import SupabaseService
from ui.assets import load_logo
from ui.mousewheel import bind_mousewheel


class PersonalDialog(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService):
        super().__init__(master)
        self.title("Personal - Meseros")
        self.geometry("1020x640")
        self.minsize(980, 620)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.selected_id: str | None = None
        self.nombre_var = tk.StringVar()
        self.activo_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.filter_estado_var = tk.StringVar(value="TODOS")
        self.status_var = tk.StringVar(value="")
        self._rows: list[dict] = []

        self._build_ui()
        self._load_meseros()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        self.logo_img = load_logo(40)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg="#1f2937").pack(side="left", padx=(12, 6), pady=12)
        ctk.CTkLabel(header, text="PERSONAL - MESEROS", font=("Arial", 18, "bold"), text_color="white").pack(side="left", padx=(6, 12), pady=12)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=12)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(6, weight=1)
        ctk.CTkLabel(form, text="Nombre:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.nombre_var, width=260).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkCheckBox(form, text="Activo", variable=self.activo_var).grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ttk.Button(form, text="Guardar", style="Accent.TButton", command=self._guardar).grid(row=0, column=3, padx=6, pady=6, sticky="ew")
        ttk.Button(form, text="Nuevo", command=self._nuevo).grid(row=0, column=4, padx=6, pady=6, sticky="ew")
        ttk.Button(form, text="Eliminar", command=self._eliminar).grid(row=0, column=5, padx=6, pady=6, sticky="ew")
        ttk.Button(form, text="Activar/Desactivar", command=self._toggle_activo).grid(row=1, column=3, columnspan=2, padx=6, pady=(0, 6), sticky="ew")
        ttk.Button(form, text="Refrescar", command=self._load_meseros).grid(row=1, column=5, padx=6, pady=(0, 6), sticky="ew")

        tools = ctk.CTkFrame(self)
        tools.pack(fill="x", padx=12, pady=(0, 8))
        tools.grid_columnconfigure(6, weight=1)
        ctk.CTkLabel(
            tools,
            text="Selecciona un mesero para editar. Guardar crea o actualiza según selección.",
            text_color="#334155",
            font=("Arial", 12, "bold"),
        ).grid(row=0, column=0, columnspan=7, padx=8, pady=(8, 4), sticky="w")

        ctk.CTkLabel(tools, text="Buscar:").grid(row=1, column=0, padx=(8, 4), pady=6, sticky="e")
        self.search_entry = ctk.CTkEntry(tools, textvariable=self.search_var, width=220)
        self.search_entry.grid(row=1, column=1, padx=4, pady=6, sticky="w")
        self.search_entry.bind("<KeyRelease>", lambda _e: self._apply_filters())

        ctk.CTkLabel(tools, text="Estado:").grid(row=1, column=2, padx=(10, 4), pady=6, sticky="e")
        self.estado_menu = ttk.Combobox(
            tools,
            textvariable=self.filter_estado_var,
            values=["TODOS", "ACTIVOS", "INACTIVOS"],
            state="readonly",
            width=13,
        )
        self.estado_menu.grid(row=1, column=3, padx=4, pady=6, sticky="w")
        self.estado_menu.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())
        ttk.Button(tools, text="Limpiar filtro", command=self._clear_filters).grid(row=1, column=6, padx=4, pady=6, sticky="e")

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=("nombre", "activo"), show="headings", height=14)
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("activo", text="Activo")
        self.tree.column("nombre", width=620, anchor="w")
        self.tree.column("activo", width=120, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f8fafc")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        bind_mousewheel(self.tree, self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        status = ctk.CTkFrame(self, fg_color="transparent")
        status.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(status, textvariable=self.status_var, text_color="#475569").pack(side="left", padx=6)
        ctk.CTkLabel(
            status,
            text="Atajos: Ctrl+S guardar, Delete borrar, Ctrl+D activar/desactivar, Ctrl+F buscar, Esc.",
            text_color="#64748b",
        ).pack(side="right", padx=6)

        self.bind("<Control-s>", self._shortcut_save)
        self.bind("<Delete>", self._shortcut_delete)
        self.bind("<Control-d>", self._shortcut_toggle)
        self.bind("<Control-f>", self._shortcut_focus_search)
        self.bind("<Escape>", self._shortcut_escape)

    def _load_meseros(self):
        try:
            meseros = self.db.listar_meseros()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar personal:\n{e}")
            return
        self._rows = sorted(
            list(meseros),
            key=lambda m: (
                0 if bool(m.get("activo")) else 1,
                str(m.get("nombre") or "").lower(),
            ),
        )
        self._render_tree()
        if self.selected_id is not None:
            sid = str(self.selected_id)
            if sid in self.tree.get_children():
                self.tree.selection_set(sid)
                self.tree.focus(sid)

    def _render_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for idx, m in enumerate(self._filtered_rows()):
            activo = "SI" if m.get("activo") else "NO"
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=str(m["id"]), values=(m.get("nombre") or "", activo), tags=(tag,))
        visible = len(self.tree.get_children())
        total = len(self._rows)
        self.status_var.set(f"{visible} visibles de {total} meseros.")

    def _filtered_rows(self) -> list[dict]:
        q = (self.search_var.get() or "").strip().lower()
        estado = (self.filter_estado_var.get() or "TODOS").strip().upper()
        rows: list[dict] = []
        for m in self._rows:
            nombre = str(m.get("nombre") or "")
            activo = bool(m.get("activo"))
            if estado == "ACTIVOS" and not activo:
                continue
            if estado == "INACTIVOS" and activo:
                continue
            if q and q not in nombre.lower():
                continue
            rows.append(m)
        return rows

    def _apply_filters(self):
        self._render_tree()

    def _clear_filters(self):
        self.search_var.set("")
        self.filter_estado_var.set("TODOS")
        self._render_tree()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        mesero_id = sel[0]
        values = self.tree.item(mesero_id, "values")
        if not values:
            return
        self.selected_id = str(mesero_id)
        self.nombre_var.set(values[0])
        self.activo_var.set(values[1] == "SI")

    def _nuevo(self):
        self.selected_id = None
        self.nombre_var.set("")
        self.activo_var.set(True)
        for iid in self.tree.selection():
            self.tree.selection_remove(iid)
        self.status_var.set("Formulario limpio para nuevo mesero.")

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "Escribe el nombre del mesero.")
            return
        try:
            activo = self.activo_var.get()
            if self.selected_id:
                updated = self.db.actualizar_mesero(self.selected_id, nombre=nombre, activo=activo)
                self.selected_id = str(updated.get("id") or self.selected_id)
                status_msg = "Mesero actualizado."
            else:
                created = self.db.crear_mesero(nombre, activo=activo)
                if created.get("id"):
                    self.selected_id = str(created.get("id"))
                status_msg = "Mesero creado."
            self._load_meseros()
            self.status_var.set(status_msg)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar mesero:\n{self._format_mesero_error(e)}")

    def _require_selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selecciona mesero", "Selecciona un mesero de la lista.")
            return None
        return str(sel[0])

    def _toggle_activo(self, _e=None):
        mesero_id = self._require_selected()
        if not mesero_id:
            return
        values = self.tree.item(mesero_id, "values") or ()
        activo_actual = bool(values and values[1] == "SI")
        try:
            self.db.actualizar_mesero(mesero_id, activo=not activo_actual)
            self.selected_id = mesero_id
            self._load_meseros()
            self.activo_var.set(not activo_actual)
            self.status_var.set("Estado de mesero actualizado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar mesero:\n{self._format_mesero_error(e)}")

    def _eliminar(self):
        mesero_id = self._require_selected()
        if not mesero_id:
            return
        nombre = self.nombre_var.get().strip() or "este mesero"
        ok = messagebox.askyesno(
            "Eliminar personal",
            (
                f"¿Eliminar a '{nombre}'?\n"
                "Esta acción es permanente."
            ),
        )
        if not ok:
            return
        try:
            self.db.eliminar_mesero(mesero_id)
            self.selected_id = None
            self._load_meseros()
            self._nuevo()
            self.status_var.set("Mesero eliminado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar mesero:\n{self._format_mesero_error(e)}")

    @staticmethod
    def _format_mesero_error(error: Exception) -> str:
        msg = str(error)
        lower = msg.lower()
        if "propinas_mesero_id_fkey" in lower or ("foreign key" in lower and "propinas" in lower):
            return (
                f"{msg}\n\n"
                "No se puede eliminar porque tiene propinas asociadas.\n"
                "Puedes desactivarlo para que no aparezca en el POS."
            )
        return msg

    def _has_active_filters(self) -> bool:
        if (self.search_var.get() or "").strip():
            return True
        return (self.filter_estado_var.get() or "TODOS").strip().upper() != "TODOS"

    def _shortcut_save(self, _event=None):
        self._guardar()
        return "break"

    def _shortcut_delete(self, _event=None):
        self._eliminar()
        return "break"

    def _shortcut_toggle(self, _event=None):
        self._toggle_activo()
        return "break"

    def _shortcut_focus_search(self, _event=None):
        self.search_entry.focus_set()
        return "break"

    def _shortcut_escape(self, _event=None):
        if self._has_active_filters():
            self._clear_filters()
        else:
            self._nuevo()
        return "break"


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    db = SupabaseService()
    dlg = PersonalDialog(root, db)
    dlg.mainloop()
