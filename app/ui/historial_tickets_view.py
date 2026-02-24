from __future__ import annotations

from datetime import date, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import customtkinter as ctk

from domain.auth import Role
from domain.ticket import build_ticket_text
from services.auth_service import AuthService
from services.supabase_service import SupabaseService
from ui.payments_dialog import ask_split_payments
from ui.ticket_preview import TicketPreview


def _to_float(raw: object, *, default: float = 0.0) -> float:
    txt = str(raw or "").strip()
    if not txt:
        return default
    try:
        return float(txt)
    except Exception:
        return default


def _calc_subtotal(precio_unitario: float, cantidad: int) -> float:
    return round(float(precio_unitario) * int(cantidad), 2)


class ItemEditorDialog(ctk.CTkToplevel):
    def __init__(self, master, *, productos: list[dict], item: dict | None = None):
        super().__init__(master)
        self.title("Editar producto")
        self.geometry("560x250")
        self.minsize(520, 220)
        self.resizable(True, False)
        self.grab_set()

        self._productos = [dict(p) for p in (productos or [])]
        self._by_label: dict[str, dict] = {}
        self.result: dict | None = None

        self.producto_var = tk.StringVar()
        self.cantidad_var = tk.StringVar()
        self.precio_var = tk.StringVar()

        self._build_ui()
        self._seed(item or {})

    def _build_ui(self):
        wrap = ctk.CTkFrame(self)
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        wrap.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(wrap, text="Producto:", font=("Arial", 13, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.producto_combo = ttk.Combobox(wrap, textvariable=self.producto_var, state="readonly")
        self.producto_combo.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        self.producto_combo.bind("<<ComboboxSelected>>", self._on_producto_selected)

        ctk.CTkLabel(wrap, text="Cantidad:", font=("Arial", 13, "bold")).grid(row=1, column=0, padx=8, pady=8, sticky="w")
        ttk.Entry(wrap, textvariable=self.cantidad_var).grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(wrap, text="Precio unitario:", font=("Arial", 13, "bold")).grid(row=2, column=0, padx=8, pady=8, sticky="w")
        ttk.Entry(wrap, textvariable=self.precio_var).grid(row=2, column=1, padx=8, pady=8, sticky="ew")

        note = ctk.CTkLabel(
            wrap,
            text="El subtotal se calcula automaticamente como cantidad x precio.",
            text_color="#64748b",
        )
        note.grid(row=3, column=0, columnspan=2, padx=8, pady=(2, 6), sticky="w")

        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, padx=8, pady=8, sticky="e")
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="left", padx=4)
        ttk.Button(actions, text="Guardar", style="Accent.TButton", command=self._save).pack(side="left", padx=4)

    def _seed(self, item: dict):
        labels: list[str] = []
        for prod in self._productos:
            pid = int(prod.get("id") or 0)
            nombre = str(prod.get("nombre") or "Producto")
            categoria = str(prod.get("categoria") or "GENERAL")
            label = f"{pid} - {nombre} ({categoria})"
            self._by_label[label] = prod
            labels.append(label)
        self.producto_combo.configure(values=labels)

        item_pid = int(item.get("producto_id") or 0)
        match_label = ""
        for label, prod in self._by_label.items():
            if int(prod.get("id") or 0) == item_pid:
                match_label = label
                break
        if not match_label and labels:
            match_label = labels[0]
        if match_label:
            self.producto_var.set(match_label)

        cantidad = int(item.get("cantidad") or 1)
        self.cantidad_var.set(str(max(1, cantidad)))

        precio = _to_float(item.get("precio_unitario"), default=0.0)
        if precio <= 0 and match_label:
            precio = _to_float(self._by_label.get(match_label, {}).get("precio"), default=0.0)
        self.precio_var.set(f"{precio:.2f}")

    def _on_producto_selected(self, _event=None):
        prod = self._by_label.get(self.producto_var.get())
        if not prod:
            return
        self.precio_var.set(f"{_to_float(prod.get('precio'), default=0.0):.2f}")

    def _save(self):
        label = self.producto_var.get().strip()
        prod = self._by_label.get(label)
        if not prod:
            messagebox.showwarning("Producto", "Selecciona un producto valido.")
            return

        try:
            cantidad = int((self.cantidad_var.get() or "").strip())
            if cantidad <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Producto", "Cantidad invalida. Debe ser entero > 0.")
            return

        try:
            precio = float((self.precio_var.get() or "").strip())
            if precio < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Producto", "Precio invalido. Debe ser numero >= 0.")
            return

        producto_id = int(prod.get("id") or 0)
        nombre = str(prod.get("nombre") or "Producto")
        subtotal = _calc_subtotal(precio, cantidad)
        self.result = {
            "producto_id": producto_id,
            "nombre_snapshot": nombre,
            "precio_unitario": round(precio, 2),
            "cantidad": cantidad,
            "subtotal": subtotal,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class TicketDetailDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        detail: dict,
        on_edit=None,
        on_cancel=None,
        on_reprint_latest=None,
        on_reprint_original=None,
    ):
        super().__init__(master)
        self.title("Detalle de ticket")
        self.geometry("1160x720")
        self.minsize(1060, 640)
        self.resizable(True, True)
        self.grab_set()

        self._detail = detail or {}
        self._on_edit = on_edit
        self._on_cancel = on_cancel
        self._on_reprint_latest = on_reprint_latest
        self._on_reprint_original = on_reprint_original
        self._build_ui()

    def _build_ui(self):
        comanda = self._detail.get("comanda") or {}
        items = self._detail.get("items") or []
        pagos = self._detail.get("pagos") or []
        tickets = self._detail.get("tickets") or []

        head = ctk.CTkFrame(self, fg_color="#1f2937", corner_radius=0, height=56)
        head.pack(fill="x", side="top")
        ctk.CTkLabel(head, text="DETALLE DE TICKET", font=("Arial", 16, "bold"), text_color="white").pack(
            side="left", padx=12, pady=12
        )

        meta = ctk.CTkFrame(self)
        meta.pack(fill="x", padx=12, pady=(10, 8))
        txt = (
            f"Folio: {comanda.get('folio') or '-'}   "
            f"Fecha: {str(comanda.get('created_at') or '').replace('T', ' ')[:19]}   "
            f"Mesa: {comanda.get('mesa') or '-'}   "
            f"Mesero: {comanda.get('mesero') or '-'}   "
            f"Estado: {str(comanda.get('status') or 'PAGADA').upper()}   "
            f"Total: ${_to_float(comanda.get('total')):.2f}"
        )
        ctk.CTkLabel(meta, text=txt, text_color="#334155").pack(side="left", padx=8, pady=8)

        guide = ctk.CTkFrame(self, fg_color="#eef2ff")
        guide.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            guide,
            text=(
                "Guia: revisa productos y pagos aqui. Para modificar usa 'Editar ticket'. "
                "Cancelar equivale a borrado logico auditado."
            ),
            text_color="#1e293b",
        ).pack(side="left", padx=8, pady=8)

        # Acciones primarias arriba para que siempre sean visibles.
        top_actions = ctk.CTkFrame(self, fg_color="transparent")
        top_actions.pack(fill="x", padx=12, pady=(0, 8))
        if self._on_edit is not None:
            ttk.Button(top_actions, text="Editar ticket", command=self._on_edit).pack(side="left", padx=4)
        if self._on_cancel is not None:
            ttk.Button(top_actions, text="Cancelar ticket", command=self._on_cancel).pack(side="left", padx=4)
        if self._on_reprint_latest is not None:
            ttk.Button(top_actions, text="Reimprimir ultima", command=self._on_reprint_latest).pack(side="left", padx=4)
        if self._on_reprint_original is not None:
            ttk.Button(top_actions, text="Reimprimir original", command=self._on_reprint_original).pack(side="left", padx=4)
        ttk.Button(top_actions, text="Cerrar", command=self.destroy).pack(side="right", padx=4)

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(body, text="Productos", font=("Arial", 13, "bold")).grid(row=0, column=0, padx=6, pady=(8, 2), sticky="w")
        tree_items = ttk.Treeview(body, columns=("producto", "cant", "pu", "sub"), show="headings", height=10)
        tree_items.heading("producto", text="Producto")
        tree_items.heading("cant", text="Cant")
        tree_items.heading("pu", text="P. Unit")
        tree_items.heading("sub", text="Subtotal")
        tree_items.column("producto", width=410, anchor="w")
        tree_items.column("cant", width=70, anchor="center")
        tree_items.column("pu", width=110, anchor="e")
        tree_items.column("sub", width=120, anchor="e")
        tree_items.grid(row=1, column=0, padx=6, pady=4, sticky="nsew")
        scroll_items_y = ttk.Scrollbar(body, orient="vertical", command=tree_items.yview)
        scroll_items_y.grid(row=1, column=0, padx=(0, 0), pady=4, sticky="nse")
        scroll_items_x = ttk.Scrollbar(body, orient="horizontal", command=tree_items.xview)
        scroll_items_x.grid(row=1, column=0, padx=6, pady=(0, 0), sticky="sew")
        tree_items.configure(yscrollcommand=scroll_items_y.set, xscrollcommand=scroll_items_x.set)
        for it in items:
            tree_items.insert(
                "",
                "end",
                values=(
                    it.get("nombre_snapshot") or "-",
                    int(it.get("cantidad") or 0),
                    f"${_to_float(it.get('precio_unitario')):.2f}",
                    f"${_to_float(it.get('subtotal')):.2f}",
                ),
            )

        ctk.CTkLabel(body, text="Pagos", font=("Arial", 13, "bold")).grid(row=0, column=1, padx=6, pady=(8, 2), sticky="w")
        tree_pagos = ttk.Treeview(body, columns=("ord", "metodo", "monto", "tip", "recibido", "cambio"), show="headings", height=10)
        tree_pagos.heading("ord", text="#")
        tree_pagos.heading("metodo", text="Metodo")
        tree_pagos.heading("monto", text="Monto")
        tree_pagos.heading("tip", text="Propina")
        tree_pagos.heading("recibido", text="Recibido")
        tree_pagos.heading("cambio", text="Cambio")
        tree_pagos.column("ord", width=45, anchor="center")
        tree_pagos.column("metodo", width=120, anchor="center")
        tree_pagos.column("monto", width=105, anchor="e")
        tree_pagos.column("tip", width=105, anchor="e")
        tree_pagos.column("recibido", width=110, anchor="e")
        tree_pagos.column("cambio", width=110, anchor="e")
        tree_pagos.grid(row=1, column=1, padx=6, pady=4, sticky="nsew")
        scroll_pagos_y = ttk.Scrollbar(body, orient="vertical", command=tree_pagos.yview)
        scroll_pagos_y.grid(row=1, column=1, padx=(0, 0), pady=4, sticky="nse")
        scroll_pagos_x = ttk.Scrollbar(body, orient="horizontal", command=tree_pagos.xview)
        scroll_pagos_x.grid(row=1, column=1, padx=6, pady=(0, 0), sticky="sew")
        tree_pagos.configure(yscrollcommand=scroll_pagos_y.set, xscrollcommand=scroll_pagos_x.set)
        for p in pagos:
            tree_pagos.insert(
                "",
                "end",
                values=(
                    int(p.get("orden") or 0),
                    str(p.get("metodo_pago") or "-"),
                    f"${_to_float(p.get('monto')):.2f}",
                    f"${_to_float(p.get('propina')):.2f}",
                    "-" if p.get("recibido") in (None, "") else f"${_to_float(p.get('recibido')):.2f}",
                    "-" if p.get("cambio") in (None, "") else f"${_to_float(p.get('cambio')):.2f}",
                ),
            )

        ctk.CTkLabel(body, text="Historial de versiones", font=("Arial", 13, "bold")).grid(
            row=2, column=0, columnspan=2, padx=6, pady=(10, 2), sticky="w"
        )
        tree_versions = ttk.Treeview(body, columns=("ver", "tipo", "fecha", "by"), show="headings", height=6)
        tree_versions.heading("ver", text="Version")
        tree_versions.heading("tipo", text="Tipo")
        tree_versions.heading("fecha", text="Fecha")
        tree_versions.heading("by", text="Creado por")
        tree_versions.column("ver", width=80, anchor="center")
        tree_versions.column("tipo", width=120, anchor="center")
        tree_versions.column("fecha", width=190, anchor="center")
        tree_versions.column("by", width=150, anchor="center")
        tree_versions.grid(row=3, column=0, columnspan=2, padx=6, pady=4, sticky="nsew")
        if tickets:
            for t in tickets:
                tree_versions.insert(
                    "",
                    "end",
                    values=(
                        int(t.get("version") or 0),
                        str(t.get("tipo") or "-"),
                        str(t.get("created_at") or "").replace("T", " ")[:19],
                        str(t.get("created_by") or "-"),
                    ),
                )
        else:
            tree_versions.insert("", "end", values=("-", "SIN VERSIONES", "-", "-"))

        # Footer minimal; acciones ya estan en barra superior.
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 6))


class ComandaCorrectionDialog(ctk.CTkToplevel):
    def __init__(self, master, *, comanda: dict, pagos: list[dict], items: list[dict], productos: list[dict]):
        super().__init__(master)
        self.title("Corregir comanda")
        self.geometry("1080x700")
        self.minsize(980, 620)
        self.resizable(True, True)
        self.grab_set()

        self._base = dict(comanda or {})
        self._pagos = [dict(p) for p in (pagos or [])]
        self._items = [self._normalize_item(it) for it in (items or [])]
        self._productos = [dict(p) for p in (productos or [])]
        self.result: dict | None = None

        self.mesero_var = tk.StringVar(value=str(self._base.get("mesero") or ""))
        self.mesa_var = tk.StringVar(value=str(self._base.get("mesa") or ""))
        start_total = _to_float(self._base.get("total"), default=0.0)
        if self._items:
            start_total = self._items_total()
        self.total_var = tk.StringVar(value=f"{start_total:.2f}")
        self._payments_summary_var = tk.StringVar(value=self._payments_summary())

        self._build_ui()
        self._refresh_items_tree()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", corner_radius=0, height=56)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="CORREGIR COMANDA", font=("Arial", 16, "bold"), text_color="white").pack(
            side="left", padx=12, pady=12
        )

        form = ctk.CTkFrame(self)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        form.grid_columnconfigure(1, weight=1)
        form.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(form, text="Mesero:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.mesero_var).grid(row=0, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(form, text="Mesa:").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.mesa_var).grid(row=1, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(form, text="Total corregido:").grid(row=2, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkEntry(form, textvariable=self.total_var).grid(row=2, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(form, text="Pagos:").grid(row=3, column=0, padx=8, pady=6, sticky="nw")
        pay_wrap = ctk.CTkFrame(form, fg_color="#eef2ff")
        pay_wrap.grid(row=3, column=1, padx=8, pady=6, sticky="ew")
        ctk.CTkLabel(pay_wrap, textvariable=self._payments_summary_var, text_color="#1f2937").pack(
            side="left", padx=8, pady=8
        )
        ttk.Button(pay_wrap, text="Editar pagos", command=self._edit_pagos).pack(side="right", padx=8, pady=8)

        ctk.CTkLabel(form, text="Productos:").grid(row=4, column=0, padx=8, pady=6, sticky="nw")
        items_wrap = ctk.CTkFrame(form)
        items_wrap.grid(row=4, column=1, padx=8, pady=6, sticky="nsew")
        items_wrap.grid_columnconfigure(0, weight=1)
        items_wrap.grid_rowconfigure(0, weight=1)

        self.items_tree = ttk.Treeview(items_wrap, columns=("producto", "cant", "pu", "sub"), show="headings", height=8)
        self.items_tree.heading("producto", text="Producto")
        self.items_tree.heading("cant", text="Cant")
        self.items_tree.heading("pu", text="P. Unit")
        self.items_tree.heading("sub", text="Subtotal")
        self.items_tree.column("producto", width=300, anchor="w")
        self.items_tree.column("cant", width=70, anchor="center")
        self.items_tree.column("pu", width=100, anchor="e")
        self.items_tree.column("sub", width=100, anchor="e")
        self.items_tree.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 6))
        items_scroll = ttk.Scrollbar(items_wrap, orient="vertical", command=self.items_tree.yview)
        items_scroll.grid(row=0, column=1, sticky="ns", pady=(0, 6))
        self.items_tree.configure(yscrollcommand=items_scroll.set)

        item_btns = ctk.CTkFrame(items_wrap, fg_color="transparent")
        item_btns.grid(row=1, column=0, columnspan=2, sticky="e")
        ttk.Button(item_btns, text="Agregar", command=self._add_item).pack(side="left", padx=4)
        ttk.Button(item_btns, text="Editar", command=self._edit_item).pack(side="left", padx=4)
        ttk.Button(item_btns, text="Quitar", command=self._remove_item).pack(side="left", padx=4)
        ttk.Button(item_btns, text="Total = productos", command=self._sync_total_with_items).pack(side="left", padx=4)

        ctk.CTkLabel(form, text="Motivo:").grid(row=5, column=0, padx=8, pady=6, sticky="nw")
        self.motivo_entry = ctk.CTkTextbox(form, height=92)
        self.motivo_entry.grid(row=5, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(
            form,
            text="La correccion queda auditada con before/after, usuario y fecha.",
            text_color="#6b7280",
        ).grid(row=6, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="w")

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=7, column=0, columnspan=2, padx=8, pady=(4, 0), sticky="e")
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="left", padx=4)
        ttk.Button(actions, text="Guardar correccion", style="Accent.TButton", command=self._save).pack(
            side="left", padx=4
        )

    def _normalize_item(self, raw: dict) -> dict:
        cantidad = int(raw.get("cantidad") or 0)
        precio = round(_to_float(raw.get("precio_unitario"), default=0.0), 2)
        subtotal = _calc_subtotal(precio, cantidad)
        return {
            "producto_id": int(raw.get("producto_id") or 0),
            "nombre_snapshot": str(raw.get("nombre_snapshot") or "Producto"),
            "precio_unitario": precio,
            "cantidad": cantidad,
            "subtotal": subtotal,
        }

    def _items_total(self) -> float:
        return round(sum(_to_float(it.get("subtotal"), default=0.0) for it in self._items), 2)

    def _sync_total_with_items(self):
        self.total_var.set(f"{self._items_total():.2f}")

    def _payments_summary(self) -> str:
        if not self._pagos:
            return "Sin pagos cargados"
        chunks: list[str] = []
        for p in self._pagos:
            metodo = str(p.get("metodo_pago") or "?")
            monto = _to_float(p.get("monto"), default=0.0)
            prop = _to_float(p.get("propina"), default=0.0)
            chunks.append(f"{metodo}: ${monto:.2f} (tip ${prop:.2f})")
        return " | ".join(chunks)

    def _refresh_items_tree(self):
        for iid in self.items_tree.get_children():
            self.items_tree.delete(iid)
        for idx, it in enumerate(self._items):
            self.items_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    it.get("nombre_snapshot") or "-",
                    int(it.get("cantidad") or 0),
                    f"${_to_float(it.get('precio_unitario')):.2f}",
                    f"${_to_float(it.get('subtotal')):.2f}",
                ),
            )
        if not self._items:
            self.items_tree.insert("", "end", iid="empty", values=("Sin productos", "-", "-", "-"))

    def _add_item(self):
        dlg = ItemEditorDialog(self, productos=self._productos, item=None)
        self.wait_window(dlg)
        if not dlg.result:
            return
        self._items.append(self._normalize_item(dlg.result))
        self._refresh_items_tree()
        self._sync_total_with_items()

    def _selected_item_index(self) -> int | None:
        selected = self.items_tree.selection()
        if not selected:
            messagebox.showwarning("Productos", "Selecciona un producto.")
            return None
        iid = str(selected[0])
        if iid == "empty":
            messagebox.showwarning("Productos", "No hay productos para editar.")
            return None
        try:
            idx = int(iid)
        except Exception:
            return None
        if not (0 <= idx < len(self._items)):
            return None
        return idx

    def _edit_item(self):
        idx = self._selected_item_index()
        if idx is None:
            return
        current = self._items[idx]
        dlg = ItemEditorDialog(self, productos=self._productos, item=current)
        self.wait_window(dlg)
        if not dlg.result:
            return
        self._items[idx] = self._normalize_item(dlg.result)
        self._refresh_items_tree()
        self._sync_total_with_items()

    def _remove_item(self):
        idx = self._selected_item_index()
        if idx is None:
            return
        if not messagebox.askyesno("Productos", "Quitar producto seleccionado?"):
            return
        self._items.pop(idx)
        self._refresh_items_tree()
        self._sync_total_with_items()

    def _edit_pagos(self):
        total = _to_float(self.total_var.get(), default=-1)
        if total <= 0:
            messagebox.showwarning("Correccion", "Total corregido invalido. Debe ser > 0 antes de editar pagos.")
            return
        rows = ask_split_payments(self, total=total, initial_rows=self._pagos)
        if rows is None:
            return
        self._pagos = rows
        self._payments_summary_var.set(self._payments_summary())

    def _save(self):
        mesero = self.mesero_var.get().strip()
        mesa = self.mesa_var.get().strip()
        total = _to_float(self.total_var.get(), default=-1)
        motivo = (self.motivo_entry.get("1.0", "end") or "").strip()

        if not mesero:
            messagebox.showwarning("Correccion", "Mesero es obligatorio.")
            return
        if not self._items:
            messagebox.showwarning("Correccion", "Debes dejar al menos un producto.")
            return
        if total <= 0:
            messagebox.showwarning("Correccion", "Total invalido. Debe ser mayor a 0.")
            return
        if len(motivo) < 4:
            messagebox.showwarning("Correccion", "Motivo debe tener al menos 4 caracteres.")
            return
        if not self._pagos:
            messagebox.showwarning("Correccion", "Debes capturar al menos un pago.")
            return

        normalized_items: list[dict] = []
        for idx, raw in enumerate(self._items, start=1):
            item = self._normalize_item(raw)
            if item["cantidad"] <= 0:
                messagebox.showwarning("Correccion", f"Cantidad invalida en producto #{idx}.")
                return
            if item["precio_unitario"] < 0:
                messagebox.showwarning("Correccion", f"Precio invalido en producto #{idx}.")
                return
            normalized_items.append(item)

        suma_pagos = round(sum(_to_float(p.get("monto"), default=0.0) for p in self._pagos), 2)
        if abs(suma_pagos - round(total, 2)) > 0.01:
            messagebox.showwarning(
                "Correccion",
                f"La suma de pagos (${suma_pagos:.2f}) debe ser igual al total corregido (${total:.2f}).",
            )
            return

        self.result = {
            "mesero": mesero,
            "mesa": mesa,
            "total": round(total, 2),
            "motivo": motivo,
            "pagos": self._pagos,
            "items": normalized_items,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class HistorialTicketsView(ctk.CTkToplevel):
    def __init__(self, master, supabase: SupabaseService, auth: AuthService):
        super().__init__(master)
        self.title("Historial de tickets")
        self.geometry("1280x760")
        self.minsize(1120, 680)
        self.resizable(True, True)
        self.grab_set()

        self.db = supabase
        self.auth = auth
        self.rows_by_id: dict[str, dict] = {}

        today = date.today()
        self.desde_var = tk.StringVar(value=(today - timedelta(days=7)).isoformat())
        self.hasta_var = tk.StringVar(value=today.isoformat())
        self.folio_var = tk.StringVar()
        self.mesero_var = tk.StringVar()
        self.mesa_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")

        self._build_ui()
        self._load_historial()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1f2937", corner_radius=0, height=56)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="HISTORIAL DE TICKETS", font=("Arial", 16, "bold"), text_color="white").pack(
            side="left", padx=12, pady=12
        )

        filters = ctk.CTkFrame(self)
        filters.pack(fill="x", padx=12, pady=(10, 8))
        for i in range(12):
            filters.grid_columnconfigure(i, weight=(1 if i in {1, 3, 5} else 0))

        ctk.CTkLabel(filters, text="Desde:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.desde_var, width=130).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(filters, text="Hasta:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.hasta_var, width=130).grid(row=0, column=3, padx=6, pady=6, sticky="ew")

        ctk.CTkLabel(filters, text="Folio:").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.folio_var, width=100).grid(row=0, column=5, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(filters, text="Mesero:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.mesero_var, width=160).grid(row=1, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(filters, text="Mesa:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(filters, textvariable=self.mesa_var, width=120).grid(row=1, column=3, padx=6, pady=6, sticky="ew")

        ttk.Button(filters, text="Actualizar", command=self._load_historial).grid(row=0, column=8, padx=6, pady=6)
        ttk.Button(filters, text="Limpiar", command=self._clear_filters).grid(row=0, column=9, padx=6, pady=6)

        guide = ctk.CTkFrame(self, fg_color="#eef2ff")
        guide.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            guide,
            text=(
                "Como modificar: 1) Selecciona un ticket. 2) Ver detalle (o doble clic). "
                "3) Editar ticket para cambiar productos/total/pagos. 4) Reimprime o cancela si aplica."
            ),
            text_color="#1e293b",
        ).pack(side="left", padx=8, pady=8)

        table_wrap = ctk.CTkFrame(self)
        table_wrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        cols = ("fecha", "folio", "mesa", "mesero", "total", "status", "metodos")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=14)
        self.tree.heading("fecha", text="Fecha/Hora")
        self.tree.heading("folio", text="Folio")
        self.tree.heading("mesa", text="Mesa")
        self.tree.heading("mesero", text="Mesero")
        self.tree.heading("total", text="Total")
        self.tree.heading("status", text="Estado")
        self.tree.heading("metodos", text="Pagos")

        self.tree.column("fecha", width=170, anchor="center")
        self.tree.column("folio", width=90, anchor="center")
        self.tree.column("mesa", width=90, anchor="center")
        self.tree.column("mesero", width=180, anchor="w")
        self.tree.column("total", width=110, anchor="e")
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("metodos", width=460, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self._view_detail())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_selection_hint())
        self.tree.bind("<Button-3>", self._show_row_menu)
        scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(actions, text="Ver detalle (doble clic)", command=self._view_detail).pack(side="left", padx=4)
        ttk.Button(actions, text="Editar ticket (productos/total)", command=self._correct_ticket).pack(side="left", padx=4)
        ttk.Button(actions, text="Reimprimir ultima", command=lambda: self._reprint(prefer="LATEST")).pack(
            side="left", padx=4
        )
        ttk.Button(actions, text="Reimprimir original", command=lambda: self._reprint(prefer="ORIGINAL")).pack(
            side="left", padx=4
        )
        ttk.Button(actions, text="Borrar / Cancelar (soft)", command=self._cancel_comanda).pack(side="left", padx=4)

        self._row_menu = tk.Menu(self, tearoff=0)
        self._row_menu.add_command(label="Ver detalle", command=self._view_detail)
        self._row_menu.add_command(label="Editar ticket", command=self._correct_ticket)
        self._row_menu.add_separator()
        self._row_menu.add_command(label="Reimprimir ultima", command=lambda: self._reprint(prefer="LATEST"))
        self._row_menu.add_command(label="Reimprimir original", command=lambda: self._reprint(prefer="ORIGINAL"))
        self._row_menu.add_separator()
        self._row_menu.add_command(label="Borrar / Cancelar", command=self._cancel_comanda)

        status = ctk.CTkFrame(self, fg_color="transparent")
        status.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(status, textvariable=self.status_var, text_color="#475569").pack(side="left", padx=6)

    def _clear_filters(self):
        today = date.today()
        self.desde_var.set((today - timedelta(days=7)).isoformat())
        self.hasta_var.set(today.isoformat())
        self.folio_var.set("")
        self.mesero_var.set("")
        self.mesa_var.set("")
        self._load_historial()

    def _parse_dates(self) -> tuple[date, date] | None:
        try:
            desde = date.fromisoformat(self.desde_var.get().strip())
            hasta = date.fromisoformat(self.hasta_var.get().strip())
        except Exception:
            messagebox.showwarning("Historial", "Usa fechas con formato YYYY-MM-DD.")
            return None
        if hasta < desde:
            messagebox.showwarning("Historial", "La fecha hasta debe ser >= fecha desde.")
            return None
        return desde, hasta

    def _load_historial(self):
        parsed = self._parse_dates()
        if not parsed:
            return
        desde, hasta = parsed
        try:
            rows = self.db.listar_historial_comandas(
                fecha_inicio=desde,
                fecha_fin=hasta,
                folio=self.folio_var.get().strip() or None,
                mesero=self.mesero_var.get().strip() or None,
                mesa=self.mesa_var.get().strip() or None,
            )
        except Exception as exc:
            messagebox.showerror("Historial", f"No se pudo cargar historial:\n{exc}")
            return

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.rows_by_id.clear()

        for row in rows:
            cid = str(row.get("id") or "")
            if not cid:
                continue
            self.rows_by_id[cid] = row
            created_at = str(row.get("created_at") or "").replace("T", " ")[:19]
            folio = row.get("folio") or "-"
            mesa = row.get("mesa") or "-"
            mesero = row.get("mesero") or "-"
            total = _to_float(row.get("total"), default=0.0)
            status = str(row.get("status") or "PAGADA").upper()
            pagos = row.get("pagos") or []
            if pagos:
                metodos = ", ".join([f"{str(p.get('metodo_pago') or '-')}: ${_to_float(p.get('monto')):.2f}" for p in pagos])
            else:
                metodos = str(row.get("metodo_pago") or "-")

            self.tree.insert(
                "",
                "end",
                iid=cid,
                values=(created_at, folio, mesa, mesero, f"${total:.2f}", status, metodos),
            )

        if rows:
            self.status_var.set(
                f"{len(rows)} tickets cargados | Selecciona uno para ver/modificar/reimprimir/cancelar"
            )
        else:
            self.status_var.set("Sin tickets en el rango seleccionado")

    def _selected_id(self) -> str | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Historial", "Selecciona una comanda del historial.")
            return None
        return str(selected[0])

    def _selected_id_soft(self) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return str(selected[0])

    def _update_selection_hint(self):
        cid = self._selected_id_soft()
        if not cid:
            return
        row = self.rows_by_id.get(cid) or {}
        folio = row.get("folio") or "-"
        total = _to_float(row.get("total"), default=0.0)
        estado = str(row.get("status") or "PAGADA").upper()
        self.status_var.set(
            f"Seleccionado folio {folio} | Total ${total:.2f} | Estado {estado} | "
            "Acciones: Ver detalle, Editar, Reimprimir, Cancelar"
        )

    def _show_row_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self._update_selection_hint()
            try:
                self._row_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._row_menu.grab_release()

    def _require_role_for_cancel(self) -> bool:
        role = self.auth.current_role()
        return role in {Role.GERENTE, Role.DUENIO}

    def _require_role_for_correct(self) -> bool:
        return self.auth.current_role() == Role.DUENIO

    def _build_ticket_from_detail(self, detail: dict) -> str:
        com = detail.get("comanda") or {}
        items = detail.get("items") or []
        pagos = detail.get("pagos") or []
        total = _to_float(com.get("total"), default=0.0)
        propina_total = round(sum(_to_float(p.get("propina"), default=0.0) for p in pagos), 2)
        payload = {
            "negocio": "Barbacoa de Miranda",
            "folio": com.get("folio") or "N/A",
            "fecha_hora": com.get("created_at") or "",
            "mesa": com.get("mesa") or "",
            "mesero": com.get("mesero") or "",
            "metodo_pago": com.get("metodo_pago") or "",
            "propina": propina_total,
            "total": total,
            "items": items,
            "pagos": pagos,
        }
        return build_ticket_text(payload)

    def _view_detail(self):
        cid = self._selected_id()
        if not cid:
            return
        try:
            detail = self.db.get_comanda_detalle(cid)
            dlg = TicketDetailDialog(
                self,
                detail=detail,
                on_edit=self._correct_ticket,
                on_cancel=self._cancel_comanda,
                on_reprint_latest=lambda: self._reprint(prefer="LATEST"),
                on_reprint_original=lambda: self._reprint(prefer="ORIGINAL"),
            )
            self.wait_window(dlg)
        except Exception as exc:
            messagebox.showerror("Historial", f"No se pudo cargar detalle:\n{exc}")

    def _reprint(self, *, prefer: str):
        cid = self._selected_id()
        if not cid:
            return
        try:
            ticket_text = self.db.reimprimir_ticket(cid, prefer=prefer)
            TicketPreview(self, ticket_text, None)
        except Exception as exc:
            messagebox.showerror("Historial", f"No se pudo preparar reimpresion:\n{exc}")

    def _cancel_comanda(self):
        cid = self._selected_id()
        if not cid:
            return
        if not self._require_role_for_cancel():
            messagebox.showwarning("Permisos", "Borrar/Cancelar comanda requiere GERENTE o DUEÑO.")
            return
        motivo = simpledialog.askstring("Borrar / Cancelar", "Motivo de cancelacion:", parent=self)
        if motivo is None:
            return
        motivo = motivo.strip()
        if len(motivo) < 4:
            messagebox.showwarning("Borrar / Cancelar", "El motivo debe tener al menos 4 caracteres.")
            return
        try:
            self.db.cancelar_comanda(
                cid,
                motivo=motivo,
                cancelada_por=self.auth.current_role().value,
            )
            self._load_historial()
            messagebox.showinfo("Borrar / Cancelar", "Comanda cancelada correctamente.")
        except Exception as exc:
            messagebox.showerror("Borrar / Cancelar", f"No se pudo cancelar:\n{exc}")

    def _correct_ticket(self):
        cid = self._selected_id()
        if not cid:
            return
        if not self._require_role_for_correct():
            messagebox.showwarning("Permisos", "Corregir ticket requiere DUEÑO.")
            return
        try:
            detail = self.db.get_comanda_detalle(cid)
        except Exception as exc:
            messagebox.showerror("Correccion", f"No se pudo cargar la comanda:\n{exc}")
            return

        comanda = detail.get("comanda") or {}
        if str(comanda.get("status") or "").upper() == "CANCELADA":
            messagebox.showwarning("Correccion", "No puedes corregir una comanda cancelada.")
            return

        pagos = detail.get("pagos") or []
        if not pagos:
            pagos = [
                {
                    "orden": 1,
                    "metodo_pago": comanda.get("metodo_pago") or "EFECTIVO",
                    "monto": _to_float(comanda.get("total"), default=0.0),
                    "propina": 0.0,
                }
            ]
        items = detail.get("items") or []
        try:
            productos = self.db.listar_productos()
        except Exception:
            productos = self.db.get_productos()

        dlg = ComandaCorrectionDialog(self, comanda=comanda, pagos=pagos, items=items, productos=productos)
        self.wait_window(dlg)
        if not dlg.result:
            return

        payload = dlg.result
        try:
            updated = self.db.corregir_comanda(
                cid,
                motivo=payload["motivo"],
                corregido_por=self.auth.current_role().value,
                total=payload["total"],
                mesa=payload["mesa"],
                mesero=payload["mesero"],
                pagos=payload["pagos"],
                items=payload["items"],
            )
            ticket_text = self._build_ticket_from_detail(updated)
            self.db.guardar_ticket_historial(
                comanda_id=cid,
                ticket_text=ticket_text,
                tipo="CORREGIDO",
                created_by=self.auth.current_role().value,
                strict=True,
            )
            self._load_historial()
            messagebox.showinfo("Correccion", "Ticket corregido, productos actualizados y auditoria guardada.")
        except Exception as exc:
            messagebox.showerror("Correccion", f"No se pudo corregir ticket:\n{exc}")
